"""대시보드 섹션 데이터 API (T-027 2단계).

**이 파일이 랩실이 새 섹션을 만들 때 볼 참조 구현이다.** 규칙 두 가지:

1. 계산은 여기서 끝낸다. 화면(`dashboard.js`)은 받아서 그리기만 한다.
   그래야 같은 숫자가 화면·CSV·API에서 갈라지지 않는다.
2. **집계의 범위를 값과 함께 실어 보낸다.** 이 섹션만 해도 구독자는 전체 3,400여 명 기준이고
   참여율은 파일럿 25명 기준이라, 범위를 안 적으면 나란히 놓인 숫자가 거짓말을 한다.

숫자를 모으는 일은 기존 `collect_*` 함수를 그대로 재사용한다 — 관리자 5탭이 쓰는 것과
같은 함수라 화면이 둘로 갈라져도 값은 하나다.
"""

from typing import Any

from sqlmodel import Session, func, select

from app.models.newsletter import Newsletter
from app.services.admin_pages import TIER_LABELS_KO, TIER_ORDER, collect_popular, collect_scores
from app.services.admin_status import collect_stats
from app.services.newsletter_template import CATEGORY_LABELS_KO

TOP_N = 10


def _rate(part: int, whole: int) -> float | None:
    """비율(%) — 분모가 0이면 0%가 아니라 '모름'이다. 둘을 섞으면 안 된다."""
    return round(part * 100 / whole, 1) if whole else None


def newsletter_section(session: Session) -> dict[str, Any]:
    """04 Newsletter 섹션이 그릴 데이터 전부."""
    stats = collect_stats(session)
    popular = collect_popular(session)
    scores = collect_scores(session)

    editions = session.exec(select(func.count()).select_from(Newsletter)).one()

    rows = scores["rows"]
    sends = sum(r["sends"] for r in rows)
    engaged = sum(r["engaged"] for r in rows)
    clicked = sum(r["clicked"] for r in rows)
    pilot_n = len(rows)

    return {
        "subtitle": (
            f"발송 {editions}편 · 참여 지표는 파일럿 {pilot_n}명 기준 · "
            f"클릭 집계는 최근 {popular['days']}일"
        ),
        "kpis": [
            {
                "label": "구독자",
                "value": stats["members"]["subscribed"],
                "unit": "명",
                "note": "전체 명단",
            },
            {"label": "발송한 편", "value": editions, "unit": "편", "note": "누적"},
            {
                "label": "열람률",
                "value": _rate(engaged, sends),
                "unit": "%",
                "note": f"파일럿 {pilot_n}명",
            },
            {
                "label": "클릭률",
                "value": _rate(clicked, sends),
                "unit": "%",
                "note": f"파일럿 {pilot_n}명",
            },
        ],
        "categories": {
            "days": popular["days"],
            "clicks_total": popular["clicks_total"],
            "matched": popular["matched"],
            # collect_popular 는 슬러그(plant_based)를 돌려준다 — 화면에 그대로 나가면 안 된다.
            # 기존 인기분야 탭과 **같은 사전**을 써서 두 화면의 분야 이름이 갈라지지 않게 한다.
            "ranked": [
                {"label": CATEGORY_LABELS_KO.get(slug, slug), "count": n}
                for slug, n in popular["ranked"]
            ],
        },
        "dwell": popular["dwell"],
        "tiers": [
            {"key": t, "label": TIER_LABELS_KO.get(t, t), "count": n}
            for t, n in scores["tiers"]
            if t in TIER_ORDER
        ],
        # 이름은 인증 뒤에서만 나가고, **이메일은 넣지 않는다** — 이 화면은 순위를 보는 곳이지
        # 연락처를 보는 곳이 아니다. 명단이 필요하면 참여도 탭의 CSV 내보내기를 쓴다.
        # tier_key 를 함께 보낸다 — 화면이 한글 라벨로 색을 고르면 라벨이 바뀔 때 조용히 어긋난다.
        # (실제로 JS에 "미상"이라 적어뒀다가 실제 라벨이 "판단 보류"인 걸 뒤늦게 발견했다.)
        "top": [
            {
                "rank": i + 1,
                "name": r["name"],
                "tier_key": r["tier"],
                "tier": TIER_LABELS_KO.get(r["tier"], r["tier"]),
                "score": round(r["score"], 1),
            }
            for i, r in enumerate(rows[:TOP_N])
        ],
    }
