"""Activity Score — 참여 이력을 0~100 점수와 등급으로 환산한다 (T-017).

프로젝트의 핵심 가치 "추적 → 점수 → 분류"의 두 번째·세 번째 단계. 행사·베네핏을 줄 회원을
고르는 근거이므로 **설명 가능해야 한다** — 왜 이 점수인지 근거 내역(ScoreResult)을 함께 낸다.

설계 요점 (실데이터 25명·9회 발송으로 검증, 근거는 T-017 티켓):
- 편(newsletter)당 최고 행동 하나만 센다. 같은 편 재열람 22회가 점수를 올리지 않는다.
  실측: raw open 22회인 회원이 있고, 반대로 open 0인데 클릭 5회인 회원도 있다.
  열람 횟수는 순위 재료로 쓸 수 없다.
- 발송 대비 비율 + 축소(K) — 발송이 1건뿐인 회원이 만점으로 상위권을 차지하지 않게.
- 반감기 감쇠 — "지금 살아 있는가"가 활동/비활동 분류의 질문이므로 최근 참여에 더 무게.
- 발송 후 10초 이내 열람은 스캐너·프리페치로 보고 버린다(실측 224건 중 42건). 클릭은 같은 구간이
  0건(최소 33초)이라 거르지 않는다.

가중치는 파일럿 데이터가 더 쌓이면 조정 대상이다(결정 4). 이 파일 상단 상수 한 곳만 고치면
다음 롤업에서 전원 재계산된다.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app.lib.logger import get_logger
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.send_log import SendLog

logger = get_logger("activity_score")

# --- 튜닝 상수 (결정 5: 열람 < 클릭 < 전달. '전달'은 관측 불가라 원클릭 반응이 그 자리를 대신한다)
W_OPENED = 1.0  # 프록시 오탐 때문에 최저 가중치 — 보조 신호
W_CLICKED = 3.0  # 의도가 실린 행동
W_REACTED = 5.0  # 원클릭 반응(T-013) — 답을 하러 손을 쓴 가장 강한 신호
DEPTH_STEP = 0.5  # 같은 편에서 URL을 더 누를 때마다 (훑기 vs 정독)
DEPTH_MAX_BONUS = 2.0  # 깊이 보너스 상한 (실측 최대 5개/편)
E_MAX = W_CLICKED + DEPTH_MAX_BONUS  # 한 편에서 얻을 수 있는 실질 최대 = 5.0

HALF_LIFE_DAYS = 30.0  # 감쇠 반감기
WINDOW_DAYS = 120  # 이보다 오래된 발송은 계산에서 제외 (무한 누적 방지)
SHRINKAGE_K = 3.0  # 축소: 무반응 가상 발송 3건을 늘 깔고 간다
BOT_OPEN_SECONDS = 10  # 발송 후 이 시간 안의 열람은 봇으로 간주 (결정 11)

ACTIVE_CUT = 30.0
WARM_CUT = 10.0

TIER_ACTIVE = "active"
TIER_WARM = "warm"
TIER_DORMANT = "dormant"
TIER_UNKNOWN = "unknown"  # 창 안에 발송이 없어 판단 근거가 없음 — dormant와 구분한다
TIER_UNSUBSCRIBED = "unsubscribed"


@dataclass
class Delivery:
    """발송 1건(회원 × 편)과 그 편에서 관측된 참여. 점수 계산의 단위."""

    sent_at: datetime
    opened: bool = False
    reacted: bool = False
    clicked_urls: set[str] = field(default_factory=set)

    def value(self) -> float:
        """이 편의 참여값 e — 최고 행동 하나만 센다(중복 가산 없음)."""
        if self.reacted:
            return min(W_REACTED, E_MAX)
        if self.clicked_urls:
            depth = min(DEPTH_STEP * (len(self.clicked_urls) - 1), DEPTH_MAX_BONUS)
            return min(W_CLICKED + depth, E_MAX)
        return W_OPENED if self.opened else 0.0


@dataclass(frozen=True)
class ScoreResult:
    """점수 + 등급 + 그렇게 나온 근거. 근거를 함께 내는 게 이 서비스의 계약이다."""

    score: float
    tier: str
    window_sends: int  # 창 안 발송 수 (= 분모의 표본)
    engaged_sends: int  # 그중 반응이 있었던 편 수
    clicked_sends: int  # 그중 클릭 이상이 있었던 편 수
    last_engaged_at: datetime | None


def _decay_weight(sent_at: datetime, now: datetime) -> float:
    age_days = max((now - sent_at).total_seconds() / 86400, 0.0)  # 시계 오차 방어
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def score_deliveries(
    deliveries: Iterable[Delivery], *, now: datetime, subscribed: bool = True
) -> ScoreResult:
    """발송 이력 → 점수·등급. 순수 함수 — DB를 모른다(테스트가 값으로 검증 가능하도록)."""
    cutoff = now - timedelta(days=WINDOW_DAYS)
    numerator = denominator = 0.0
    window = engaged = clicked = 0
    last_engaged: datetime | None = None

    for d in deliveries:
        if d.sent_at < cutoff:
            continue
        window += 1
        w = _decay_weight(d.sent_at, now)
        e = d.value()
        numerator += e * w
        denominator += w
        if e > 0:
            engaged += 1
            if last_engaged is None or d.sent_at > last_engaged:
                last_engaged = d.sent_at
        if d.clicked_urls or d.reacted:
            clicked += 1

    # 분모의 +K가 축소 — 발송 1건뿐인 회원은 만점을 받아도 25점을 넘지 못한다.
    score = 100 * numerator / (E_MAX * (denominator + SHRINKAGE_K)) if window else 0.0
    return ScoreResult(
        score=round(score, 1),
        tier=tier_for(score, window_sends=window, subscribed=subscribed),
        window_sends=window,
        engaged_sends=engaged,
        clicked_sends=clicked,
        last_engaged_at=last_engaged,
    )


def tier_for(score: float, *, window_sends: int, subscribed: bool = True) -> str:
    """등급은 절대 컷으로 정한다 — 기준이 고정이어야 '왜 active인가'를 설명할 수 있다.

    백분위(상대 위치)는 저장하지 않고 화면에서 조회 시점에 계산해 병기한다(percentile_ranks).
    """
    if not subscribed:
        return TIER_UNSUBSCRIBED
    if window_sends == 0:
        return TIER_UNKNOWN  # 안 보냈으면서 비활동으로 낙인찍지 않는다
    if score >= ACTIVE_CUT:
        return TIER_ACTIVE
    if score >= WARM_CUT:
        return TIER_WARM
    return TIER_DORMANT


def percentile_ranks(scores: Mapping[int, float]) -> dict[int, int]:
    """세그먼트 안에서의 백분위(0~100, 높을수록 상위). 동점은 같은 값을 받는다."""
    values = sorted(scores.values())
    n = len(values)
    if n == 0:
        return {}
    ranks: dict[int, int] = {}
    for key, value in scores.items():
        below = sum(1 for v in values if v < value)
        same = sum(1 for v in values if v == value)
        ranks[key] = round(100 * (below + same / 2) / n)
    return ranks


def collect_deliveries(
    session: Session, member_ids: Sequence[int], *, now: datetime | None = None
) -> dict[int, list[Delivery]]:
    """발송·이벤트를 **배치로** 읽어 회원별 Delivery 목록으로 만든다.

    행당 쿼리 금지 — 원격 DB(Supabase)라 왕복이 비용이다. 세 번의 IN 쿼리로 전부 읽고
    메모리에서 (member_id, newsletter_id)로 인덱싱한다. 이벤트를 열람·반응 / 클릭 두 쿼리로
    나눈 건 클릭에만 url이 필요하기 때문 — payload(JSONB)는 어느 쪽도 읽지 않는다.
    """
    now = now or datetime.now(UTC)
    if not member_ids:
        return {}
    cutoff = now - timedelta(days=WINDOW_DAYS)

    by_key: dict[tuple[int, int], Delivery] = {}
    sent_rows = session.exec(
        select(SendLog.member_id, SendLog.newsletter_id, SendLog.created_at).where(
            col(SendLog.member_id).in_(member_ids),
            SendLog.status == "sent",
            col(SendLog.created_at) >= cutoff,
        )
    ).all()
    for member_id, newsletter_id, created_at in sent_rows:
        if member_id is None:
            continue
        key = (member_id, newsletter_id)
        prev = by_key.get(key)
        # 같은 편이 두 번 기록됐다면 첫 발송 시각을 기준으로 삼는다(감쇠·봇 판정의 기준일)
        if prev is None:
            by_key[key] = Delivery(sent_at=created_at)
        elif created_at < prev.sent_at:
            prev.sent_at = created_at

    signal_rows = session.exec(
        select(
            EngagementEvent.member_id,
            EngagementEvent.newsletter_id,
            EngagementEvent.event_type,
            EngagementEvent.occurred_at,
        ).where(
            col(EngagementEvent.member_id).in_(member_ids),
            col(EngagementEvent.event_type).in_(("opened", "reacted")),
            col(EngagementEvent.occurred_at) >= cutoff,
        )
    ).all()
    for member_id, newsletter_id, event_type, occurred_at in signal_rows:
        # 발송 기록이 없는 편의 이벤트는 버린다 — 기준일이 없어 감쇠도 봇 판정도 못 한다.
        delivery = by_key.get((member_id or 0, newsletter_id or 0))
        if delivery is None:
            continue
        if event_type == "reacted":
            delivery.reacted = True
        elif (occurred_at - delivery.sent_at).total_seconds() >= BOT_OPEN_SECONDS:
            delivery.opened = True

    click_rows = session.exec(
        select(
            EngagementEvent.member_id,
            EngagementEvent.newsletter_id,
            EngagementEvent.url,
        ).where(
            col(EngagementEvent.member_id).in_(member_ids),
            EngagementEvent.event_type == "clicked",
            col(EngagementEvent.occurred_at) >= cutoff,
        )
    ).all()
    for member_id, newsletter_id, url in click_rows:
        delivery = by_key.get((member_id or 0, newsletter_id or 0))
        if delivery is not None:
            delivery.clicked_urls.add(url or "")

    grouped: dict[int, list[Delivery]] = {mid: [] for mid in member_ids}
    for (member_id, _), delivery in by_key.items():
        grouped.setdefault(member_id, []).append(delivery)
    return grouped


def score_members(
    session: Session, member_ids: Sequence[int], *, now: datetime | None = None
) -> dict[int, ScoreResult]:
    """회원 묶음의 점수·등급을 한 번에 계산. 발송 이력이 없는 회원도 결과에 포함된다(unknown)."""
    now = now or datetime.now(UTC)
    ids = list(dict.fromkeys(member_ids))
    if not ids:
        return {}
    deliveries = collect_deliveries(session, ids, now=now)
    subscribed = {
        mid: sub
        for mid, sub in session.exec(
            select(Member.id, Member.subscribed).where(col(Member.id).in_(ids))
        ).all()
        if mid is not None
    }
    return {
        mid: score_deliveries(
            deliveries.get(mid, []), now=now, subscribed=subscribed.get(mid, True)
        )
        for mid in ids
    }
