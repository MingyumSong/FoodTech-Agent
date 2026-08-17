"""2차 게이트(뉴스레터 관련성·심도 판정)가 살아 있는지 실제 풀로 확인한다 (T-028).

**왜 스크립트인가**: 게이트는 조용히 무력화된다. 응답은 정상인데 전부 keep으로 통과시키면
숫자 어디에도 이상이 안 보이고, 발송은 성공한 채로 아파트 분양 기사가 메일 제목이 된다
(2026-08-17 푸디픽 #026). 그때 원인을 좁힌 게 이 절차라서 레포에 남긴다.

읽는 법 — **drop 0은 거의 항상 고장이다.** 운영 풀 100건 남짓이면 3~4할은 떨어져야 정상이고,
심도가 3 한 곳에 뭉쳐 있으면 판정이 아니라 체념이다(메인 선정이 최신순으로 되돌아간다).

    uv run python scripts/gate_check.py           # 지금 코드대로(청크) 판정
    uv run python scripts/gate_check.py --whole   # 풀 전체를 한 번에 — 붕괴 재현용

운영 풀로 보려면 DATABASE_URL을 SUPABASE_URL로 넘긴다(읽기만 한다. DB에 쓰지 않는다):

    DATABASE_URL="$SUPABASE_URL" uv run python scripts/gate_check.py

LLM을 호출하므로 한 번에 약 $0.01이 든다. OPENROUTER_API_KEY가 없으면 게이트는
전량 통과로 동작하니 이 스크립트도 아무것도 못 본다(그 사실을 알려준다).
"""

import sys

import httpx
from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.services.curation import curate_dicts
from app.services.news_classify import (
    _gate_batch,
    filter_foodtech_relevant,
    is_non_news_url,
)
from app.services.newsletter import _item_dict, _recent_items
from app.services.send_settings import get_send_settings

WHOLE = "--whole" in sys.argv


def main() -> int:
    if not settings.openrouter_api_key:
        print("OPENROUTER_API_KEY 없음 — 게이트는 전량 통과로 동작한다. 볼 것이 없다.")
        return 1

    with Session(engine) as session:
        cfg = get_send_settings(session)
        pool = [
            _item_dict(it)
            for it in _recent_items(session, cfg.days)
            if (it.category or "") != "general" and not is_non_news_url(it.url or "")
        ]
    before = len(pool)
    pool = curate_dicts(pool)  # 조립과 같은 순서 — 게이트는 큐레이션 뒤에 온다
    print(f"최근 {cfg.days}일 풀 {before}건 → 큐레이션 후 {len(pool)}건")
    if not pool:
        print("풀이 비었다 — 수집(/jobs/news-refresh)부터 확인할 것.")
        return 1

    with httpx.Client() as client:
        if WHOLE:
            # 일부러 통짜로 부른다. T-028 이전 동작이고, 붕괴를 눈으로 보려는 용도다.
            kept, dropped = _gate_batch(pool, client)
        else:
            kept, dropped = filter_foodtech_relevant(pool, client)

    depths: dict[int, int] = {}
    for it in kept:
        d = it.get("depth")
        depths[d if isinstance(d, int) else 0] = depths.get(d if isinstance(d, int) else 0, 0) + 1

    mode = "통짜 1회" if WHOLE else "청크 분할"
    print(f"\n=== {mode} · keep {len(kept)} / drop {len(dropped)} ===")
    print(f"심도 분포: {dict(sorted(depths.items(), reverse=True))}")

    if not dropped:
        print("\n⚠️  drop 0 — 게이트가 판정을 포기했다고 봐야 한다.")
        print("    확인 순서: 배치 크기(BATCH_SIZE) → 모델 응답 파싱(_parse_gate) → 프롬프트.")
    if len(depths) <= 1:
        print("⚠️  심도가 한 값에 뭉쳤다 — 메인 선정이 최신순으로 되돌아간다(T-024 무효).")

    print("\n--- 메인 후보 (심도 높은 순 10건) ---")
    for it in sorted(kept, key=lambda x: -(x.get("depth") or 0))[:10]:
        print(f"  d{it.get('depth', '-')} [{(it.get('region') or '')[:3]}] {it['title'][:60]}")
    print(f"\n--- 탈락 표본 (최대 15건 / 총 {len(dropped)}건) ---")
    for it in dropped[:15]:
        print(f"  {it['title'][:66]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
