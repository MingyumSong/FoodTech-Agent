"""뉴스 LLM 분류·DB 저장 (T-006).

수집된 아이템 중 DB에 없는 URL만 배치로 분류해 news_items에 저장한다.
프롬프트·배치 크기·관대한 파싱은 T-004 드라이런에서 검증된 방식 그대로.
분류 실패는 수집을 막지 않는다 — 실패분은 저장하지 않고 다음 크론에서 재시도된다.
"""

import json
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, col, select

from app.config import settings
from app.db import engine
from app.lib.logger import get_logger
from app.models.news_item import NewsItem

logger = get_logger("news_classify")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
BATCH_SIZE = 20

# 저장 라벨 = 영문 슬러그, LLM I/O = 검증된 한국어 라벨 (T-006 설계 결정 1)
# "해당없음"은 슬러그가 없다 = 저장하지 않는다 (폐기).
SLUG_BY_KO = {
    "세포배양식품": "cell_cultured",
    "식물기반식품": "plant_based",
    "간편식": "convenience",
    "식품프린팅": "food_printing",
    "스마트제조": "smart_manufacturing",
    "스마트유통": "smart_distribution",
    "커스터마이징": "customizing",
    "외식 푸드테크": "food_service",
    "업사이클링": "upcycling",
    "친환경포장": "eco_packaging",
    "일반": "general",
}
KO_BY_SLUG = {v: k for k, v in SLUG_BY_KO.items()}
DISCARD_LABEL = "해당없음"
CATEGORIES_KO = [*SLUG_BY_KO.keys(), DISCARD_LABEL]

# 검수(2026-07-21)로 뉴스가 아님이 확정된 도메인 — LLM 판정 전에 결정적으로 차단.
NON_NEWS_DOMAINS = {"wikipedia.org", "finance.yahoo.com"}

# 판정 순서·예시는 희정 검수(docs/research/뉴스분류_검수완료.md) 오분류 패턴에서 도출.
SYSTEM_PROMPT = f"""당신은 푸드테크 뉴스 분류기다. 각 항목을 아래 판정 순서에 따라
정부 "푸드테크 10대 핵심분야" 중 정확히 하나로 분류하라.

판정 순서:
1. 뉴스 기사가 아니면 "해당없음" — 백과사전 문서, 주가·시세 페이지, 포럼 질문글,
   단순 제품·매장 소개 페이지, 퀴즈 정답·쿠폰·이벤트 안내.
2. 푸드테크(식품 산업의 기술·산업 소식)와 무관하면 "해당없음" — 예: 식품과 무관한
   의료·제약·바이오, 자동차·IT 기업, 기업 승계·지배구조·주가 일반, 지자체 행정·복지·축제
   소식, 기술 요소 없는 레스토랑·맛집 소개.
3. 관련이 있으면 기사의 "핵심 주제"가 속한 분야 하나로 분류한다. 회사의 부수 사업이나
   지나가는 한 문장 언급은 분류 근거가 아니다.
4. 푸드테크 관련이지만 핵심 주제가 10대 분야 어디에도 맞지 않으면 "일반" —
   예: 스마트팜, 정밀발효, 투자·정책 일반, 협회·행사 소식, 업계 동향 모음, 식품 기업 일반 소식.
5. 확신이 없을 때: 푸드테크 여부가 애매하면 "해당없음", 분야가 애매하면 "일반".

허용 카테고리 (이 목록의 문자열을 그대로 사용):
{json.dumps(CATEGORIES_KO, ensure_ascii=False)}

출력은 JSON 배열만. 다른 텍스트·설명·코드펜스 금지:
[{{"id": 0, "category": "간편식"}}, ...]"""


def _is_non_news_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in NON_NEWS_DOMAINS)


def _call_openrouter(client: httpx.Client, batch: list[dict[str, Any]]) -> str:
    """배치 1개 분류 호출 — 재시도 포함. 최종 실패는 예외 전파(호출부가 격리)."""
    payload = {
        "model": settings.news_classify_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ],
        "max_tokens": 8000,
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    resp = None
    for attempt in range(3):
        resp = client.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""
    assert resp is not None
    resp.raise_for_status()
    return ""


def _parse_labels(text: str) -> dict[int, str]:
    """응답에서 JSON 배열을 관대하게 추출. 실패 항목은 누락시킨다 (드라이런과 동일)."""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return {}
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    labels: dict[int, str] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("category") in CATEGORIES_KO and "id" in row:
            labels[int(row["id"])] = row["category"]
    return labels


def _parse_published_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def classify_and_store(
    items: list[dict[str, Any]],
    client: httpx.Client | None = None,
    session: Session | None = None,
) -> dict[str, int]:
    """신규 URL만 LLM 분류 → "해당없음" 폐기 → news_items에 멱등 저장.

    반환: {"new": 신규, "blocked": 도메인차단, "stored": 저장, "discarded": 폐기,
          "unclassified": 실패, "existing": 기존}
    """
    if not settings.openrouter_api_key:
        logger.warning("no OPENROUTER_API_KEY — classification skipped")
        return {
            "new": 0,
            "blocked": 0,
            "stored": 0,
            "discarded": 0,
            "unclassified": 0,
            "existing": 0,
        }
    if client is None:
        with httpx.Client() as own_client:
            return classify_and_store(items, client=own_client, session=session)
    if session is None:
        with Session(engine) as own_session:
            return classify_and_store(items, client=client, session=own_session)

    urls = [it["url"] for it in items if it.get("url")]
    existing = set(session.exec(select(NewsItem.url).where(col(NewsItem.url).in_(urls))).all())
    fresh = [it for it in items if it.get("url") and it["url"] not in existing]
    new_items = [it for it in fresh if not _is_non_news_url(it["url"])]
    stats = {
        "new": len(fresh),
        "blocked": len(fresh) - len(new_items),
        "stored": 0,
        "discarded": 0,
        "unclassified": 0,
        "existing": len(existing),
    }
    if not new_items:
        return stats

    labels: dict[int, str] = {}
    for start in range(0, len(new_items), BATCH_SIZE):
        batch = new_items[start : start + BATCH_SIZE]
        payload = [
            {"id": start + i, "title": it["title"], "summary": (it.get("summary") or "")[:200]}
            for i, it in enumerate(batch)
        ]
        content = _call_openrouter(client, payload)
        labels.update(_parse_labels(content))

    now = datetime.now(UTC)
    for i, it in enumerate(new_items):
        label = labels.get(i)
        if label is None:
            stats["unclassified"] += 1
            continue
        if label == DISCARD_LABEL:
            stats["discarded"] += 1
            continue
        stmt = (
            pg_insert(NewsItem)
            .values(
                title=it["title"],
                url=it["url"],
                summary=(it.get("summary") or "")[:300],
                source=it.get("source") or "",
                origin=it.get("origin") or "",
                region=it.get("region") or "",
                category=SLUG_BY_KO[label],
                published_at=_parse_published_at(it.get("published_at")),
                collected_at=now,
            )
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(col(NewsItem.id))
        )
        if session.execute(stmt).scalar() is not None:
            stats["stored"] += 1
    session.commit()
    logger.info(f"news classified: {stats}")
    return stats
