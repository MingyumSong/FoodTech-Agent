"""기사 읽은 시간의 근사 — 연속 클릭 간격 (T-015).

**원문 기사 페이지의 실제 체류는 측정할 수 없다.** 그 페이지는 언론사 서버에서 뜨고 우리 코드를
심을 수 없다. 우리에게 오는 신호는 "링크를 눌러 떠났다"까지다.

대신 같은 회원이 **같은 편 안에서** 기사 A를 누르고 B를 누르기까지의 간격을 A를 보고 있던
시간으로 본다. 검색엔진의 long click / short click과 같은 원리.

한계를 숨기지 않는다:
- 각 (회원, 편)의 **마지막 클릭은 잴 수 없다** — 다음 클릭이 없다. 실측 기준 표본이 약 절반으로
  준다(운영 데이터: 클릭 128건 / 조합 62개 → 측정 가능 최대 66건).
- 간격에는 메일로 돌아와 다음 기사를 고르는 시간이 섞인다.
- 상한을 안 두면 "몇 시간 뒤 다시 열어 클릭"이 통째로 체류로 잡힌다 → MAX_GAP_SECONDS로 자른다.
- 편이 다르면 이어 읽은 게 아니므로 간격을 잇지 않는다.

결정 5와 같은 태도: 정밀 지표가 아니라 **상대적 순위 도구**다.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlmodel import Session, col, select

from app.models.engagement_event import EngagementEvent

# 30분을 넘으면 "이어서 읽었다"고 보기 어렵다 — 자리를 떴다가 돌아온 것으로 보고 표본에서 뺀다.
MAX_GAP_SECONDS = 1800
# 10초 안에 다음 걸 눌렀으면 제목만 보고 닫은 것(튕김).
BOUNCE_SECONDS = 10
# 1분 넘게 안 돌아왔으면 실제로 읽은 것으로 본다.
ENGAGED_SECONDS = 60

DEFAULT_DAYS = 30


def _gaps_by_pair(events: list[EngagementEvent]) -> tuple[list[float], int, int]:
    """(회원, 편)별로 시각 순 인접 간격을 뽑는다.

    반환: (상한 안쪽 간격 초 목록, 마지막 클릭이라 못 잰 수, 상한 초과로 버린 수)
    """
    by_pair: dict[tuple[int, int], list[datetime]] = defaultdict(list)
    for e in events:
        if e.member_id is None or e.newsletter_id is None:
            continue  # 고아 이벤트는 누가 언제 읽었는지 이을 수 없다
        by_pair[(e.member_id, e.newsletter_id)].append(e.occurred_at)

    gaps: list[float] = []
    unmeasurable = over_cap = 0
    for times in by_pair.values():
        times.sort()
        unmeasurable += 1  # 조합마다 마지막 1건은 다음 클릭이 없다
        for earlier, later in zip(times, times[1:], strict=False):
            seconds = (later - earlier).total_seconds()
            if seconds > MAX_GAP_SECONDS:
                over_cap += 1
            else:
                gaps.append(seconds)
    return gaps, unmeasurable, over_cap


def collect_dwell_stats(session: Session, *, days: int = DEFAULT_DAYS) -> dict[str, Any]:
    """최근 N일 클릭에서 체류 근사 통계를 낸다. PII는 담지 않는다."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    events = list(
        session.exec(
            select(EngagementEvent)
            .where(EngagementEvent.event_type == "clicked")
            .where(col(EngagementEvent.occurred_at) >= cutoff)
        ).all()
    )
    gaps, unmeasurable, over_cap = _gaps_by_pair(events)

    bounce = sum(1 for g in gaps if g < BOUNCE_SECONDS)
    engaged = sum(1 for g in gaps if g >= ENGAGED_SECONDS)
    return {
        "days": days,
        "clicks_total": len(events),
        "measurable": len(gaps),
        "unmeasurable_last": unmeasurable,
        "over_cap": over_cap,
        "median_seconds": median(gaps) if gaps else None,
        "bounce": bounce,
        "middle": len(gaps) - bounce - engaged,
        "engaged": engaged,
    }


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{int(round(seconds))}초"
    return f"{int(seconds // 60)}분 {int(round(seconds % 60))}초"
