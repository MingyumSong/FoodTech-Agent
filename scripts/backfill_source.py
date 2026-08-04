"""news_items.source 백필 (T-018).

네이버·Brave 수집기가 매체명을 빈 문자열로 넣어와 기존 행에 출처가 없다.
URL 호스트에서 되살려 채운다. 이미 값이 있는 행은 건드리지 않는다.

기본은 dry_run — 무엇이 어떻게 바뀌는지 먼저 보고 실행한다.
  uv run python scripts/backfill_source.py            # 미리보기
  uv run python scripts/backfill_source.py --apply    # 실제 반영
운영 DB에 돌리려면 DATABASE_URL을 SUPABASE_URL로 넘긴다.
"""

import sys
from collections import Counter

from sqlmodel import Session, col, select

from app.db import engine
from app.models.news_item import NewsItem
from app.services.news_sources import SOURCE_BY_DOMAIN, source_from_url


def main() -> int:
    apply = "--apply" in sys.argv

    with Session(engine) as session:
        rows = list(
            session.exec(
                select(NewsItem).where((col(NewsItem.source).is_(None)) | (NewsItem.source == ""))
            ).all()
        )
        named = Counter()
        fallback = Counter()
        empty = 0
        for item in rows:
            source = source_from_url(item.url or "")
            if not source:
                empty += 1
                continue
            (named if source in SOURCE_BY_DOMAIN.values() else fallback)[source] += 1
            if apply:
                item.source = source
                session.add(item)
        if apply:
            session.commit()

    total = sum(named.values()) + sum(fallback.values())
    print(f"출처 없는 행: {len(rows)}건")
    print(f"  매핑된 매체:   {sum(named.values())}건 ({len(named)}곳)")
    print(f"  도메인 폴백:   {sum(fallback.values())}건 ({len(fallback)}곳)")
    print(f"  못 채움(URL 이상): {empty}건")
    print()
    print("매핑 상위 10:", ", ".join(f"{k} {v}" for k, v in named.most_common(10)))
    print("폴백 상위 10:", ", ".join(f"{k} {v}" for k, v in fallback.most_common(10)))
    print()
    print(f"{'반영 완료' if apply else '미리보기 — 반영하려면 --apply'}: {total}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
