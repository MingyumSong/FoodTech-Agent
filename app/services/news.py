"""뉴스 수집 서비스 — 폴백 + 재시도 + 캐시 + 헬스체크 (T-001).

프로토타입 결함 반면교사: 소스 선택을 "키 존재 여부"가 아니라 **수집 결과**로 판단한다.
1차 소스(네이버/Brave)가 오류든 0건이든 items가 비면 RSS 폴백 풀로 넘어간다.
"""

import html
import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import feedparser
import httpx

from app.config import settings
from app.lib.http import get_with_retry
from app.lib.logger import get_logger
from app.services.news_sources import (
    BRAVE_SEARCH_API,
    DOMESTIC_FEEDS,
    FILTER_KEYWORDS,
    GOOGLE_NEWS_RSS_EN,
    NAVER_NEWS_API,
    OVERSEAS_FEEDS,
    SEARCH_QUERIES,
    RssFeed,
)

logger = get_logger("news")

MAX_ITEMS_PER_REGION = 40
BRAVE_REQUEST_INTERVAL = 1.1  # Brave 무료 플랜 rate limit(1 req/s) 준수


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return html.unescape(s)


def _matches_keywords(item: dict[str, Any]) -> bool:
    text = f"{item['title']} {item['summary']}".lower()
    return any(kw.lower() in text for kw in FILTER_KEYWORDS)


def _entry_to_item(
    entry: Any, *, source: str, origin: str, region: str, category: str
) -> dict[str, Any] | None:
    """feedparser entry → 표준 아이템. 제목/링크 없으면 None."""
    url = getattr(entry, "link", "")
    title = _strip_html(getattr(entry, "title", ""))
    if not url or not title:
        return None
    published = ""
    published_parsed = getattr(entry, "published_parsed", None)
    if published_parsed:
        published = datetime(*published_parsed[:6], tzinfo=UTC).isoformat()
    return {
        "title": title,
        "url": url,
        "summary": _strip_html(getattr(entry, "summary", ""))[:300],
        "source": source,
        "published_at": published,
        "category": category,
        "origin": origin,
        "region": region,
    }


# ---------------------------------------------------------------- fetchers


def fetch_naver(client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """네이버 뉴스 API — 국내 1차. 쿼리별 실패는 로그만 남기고 계속한다."""
    if not (settings.naver_client_id and settings.naver_client_secret):
        logger.info("naver: no credentials, skipping")
        return []
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    items: list[dict[str, Any]] = []
    for q in SEARCH_QUERIES:
        try:
            resp = get_with_retry(
                NAVER_NEWS_API,
                params={"query": q.ko, "display": 10, "sort": "date"},
                headers=headers,
                client=client,
            )
            for entry in resp.json().get("items", []):
                url = entry.get("originallink") or entry.get("link") or ""
                title = _strip_html(entry.get("title", ""))
                if not url or not title:
                    continue
                published = ""
                if entry.get("pubDate"):
                    try:
                        # UTC로 정규화해야 소스가 섞여도 문자열 정렬이 시간순과 일치한다
                        published = (
                            parsedate_to_datetime(entry["pubDate"]).astimezone(UTC).isoformat()
                        )
                    except ValueError:
                        pass
                items.append(
                    {
                        "title": title,
                        "url": url,
                        "summary": _strip_html(entry.get("description", ""))[:300],
                        "source": "",
                        "published_at": published,
                        "category": q.category,
                        "origin": "naver",
                        "region": "domestic",
                    }
                )
        except httpx.HTTPError as exc:
            logger.warning(f"naver query failed ({q.category}): {type(exc).__name__}")
    return items


def fetch_brave(
    client: httpx.Client | None = None, sleep: Callable[[float], None] | None = None
) -> list[dict[str, Any]]:
    """Brave Search API — 해외 1차. rate limit(1 req/s) 준수 위해 쿼리 사이 대기."""
    if not settings.brave_search_api_key:
        logger.info("brave: no api key, skipping")
        return []
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_search_api_key,
    }
    items: list[dict[str, Any]] = []
    for i, q in enumerate(SEARCH_QUERIES):
        if i > 0:
            (sleep or time.sleep)(BRAVE_REQUEST_INTERVAL)
        try:
            resp = get_with_retry(
                BRAVE_SEARCH_API,
                params={"q": q.en, "count": 10, "freshness": "pm"},
                headers=headers,
                client=client,
            )
            for entry in resp.json().get("web", {}).get("results", []):
                url = entry.get("url", "")
                title = _strip_html(entry.get("title", ""))
                if not url or not title:
                    continue
                items.append(
                    {
                        "title": title,
                        "url": url,
                        "summary": _strip_html(entry.get("description", ""))[:300],
                        "source": "",
                        "published_at": entry.get("page_age") or "",
                        "category": q.category,
                        "origin": "brave",
                        "region": "overseas",
                    }
                )
        except httpx.HTTPError as exc:
            logger.warning(f"brave query failed ({q.category}): {type(exc).__name__}")
    return items


def fetch_rss_pool(
    feeds: list[RssFeed], region: str, client: httpx.Client | None = None
) -> list[dict[str, Any]]:
    """RSS 폴백 풀 — 피드 하나가 죽어도 나머지는 계속 수집한다."""
    items: list[dict[str, Any]] = []
    for feed in feeds:
        try:
            resp = get_with_retry(feed.url, headers=feed.headers, client=client)
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:20]:
                item = _entry_to_item(
                    entry,
                    source=feed.name,
                    origin=f"rss:{feed.name}",
                    region=region,
                    category="일반",
                )
                if item is None:
                    continue
                if feed.keyword_filter and not _matches_keywords(item):
                    continue
                items.append(item)
        except Exception as exc:  # feedparser 예외 타입 불특정
            logger.warning(f"rss feed failed ({feed.name}): {type(exc).__name__}")
    return items


def fetch_google_news_en(client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Google News RSS(해외) — Brave와 동일 쿼리 공유 (AC4).

    링크가 news.google.com 리다이렉트 URL임에 주의 (디코딩은 T-003에서 결정).
    """
    items: list[dict[str, Any]] = []
    for q in SEARCH_QUERIES:
        url = GOOGLE_NEWS_RSS_EN.format(query=quote(q.en))
        try:
            resp = get_with_retry(url, client=client)
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:5]:
                item = _entry_to_item(
                    entry,
                    source="Google News",
                    origin="rss:google-news",
                    region="overseas",
                    category=q.category,
                )
                if item is not None:
                    items.append(item)
        except Exception as exc:  # feedparser 예외 타입 불특정
            logger.warning(f"google news rss failed ({q.category}): {type(exc).__name__}")
    return items


# ---------------------------------------------------------------- orchestrator


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)
    return deduped


def _dedupe_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = _dedupe(items)
    deduped.sort(key=lambda x: x["published_at"] or "0000", reverse=True)
    return deduped


def refresh_news_cache(client: httpx.Client | None = None) -> dict[str, Any]:
    """국내·해외 각각 1차 소스 → 실패/0건 시 RSS 폴백. 결과를 캐시 파일에 원자적으로 기록."""
    if client is None:
        # 수집 1회(수십 요청)는 커넥션 풀 하나를 공유한다
        with httpx.Client(follow_redirects=True) as shared:
            return refresh_news_cache(shared)

    domestic = fetch_naver(client)
    domestic_source = "naver"
    if not domestic:
        logger.warning("naver returned no items, falling back to domestic RSS pool")
        domestic = fetch_rss_pool(DOMESTIC_FEEDS, "domestic", client)
        domestic_source = "rss"

    overseas = fetch_brave(client)
    overseas_source = "brave"
    if not overseas:
        logger.warning("brave returned no items, falling back to overseas RSS pool")
        overseas = fetch_rss_pool(OVERSEAS_FEEDS, "overseas", client)
        overseas += fetch_google_news_en(client)
        overseas_source = "rss"

    # 같은 통신사발 기사가 양쪽 지역에 실릴 수 있어 지역별 정리 후 전역 중복제거 한 번 더
    items = _dedupe(
        _dedupe_and_sort(domestic)[:MAX_ITEMS_PER_REGION]
        + _dedupe_and_sort(overseas)[:MAX_ITEMS_PER_REGION]
    )
    cache = {
        "updated_at": datetime.now(UTC).isoformat(),
        "count": len(items),
        "sources": {"domestic": domestic_source, "overseas": overseas_source},
        "items": items,
    }
    _write_cache(cache)
    logger.info(
        f"news cache refreshed: {len(items)} items "
        f"(domestic={domestic_source}, overseas={overseas_source})"
    )
    # 분류·DB 저장 (T-006) — 실패해도 수집·캐시·헬스체크는 무관 (실패분은 다음 크론에서 재분류)
    try:
        from app.services.news_classify import classify_and_store

        cache["classify"] = classify_and_store(items, client=client)
    except Exception as exc:
        logger.error(f"news classification failed (collection unaffected): {exc}")
        cache["classify"] = {"error": str(exc)}
    return cache


def _cache_path() -> Path:
    return Path(settings.news_cache_path)


def _write_cache(cache: dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 고유 임시 파일 → 동시 refresh가 겹쳐도 서로의 쓰기를 오염시키지 않는다
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp_name, path)


def read_news_cache() -> dict[str, Any] | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------- healthcheck


def check_news_health() -> dict[str, Any]:
    """발송 전 헬스체크 — 캐시 존재·신선도·건수를 검사한다 (AC3).

    반환 dict의 ok=False면 reason에 구분 가능한 실패 신호가 담긴다:
    cache_missing / cache_corrupt / stale / too_few_items
    """
    path = _cache_path()
    if not path.exists():
        return {"ok": False, "reason": "cache_missing"}
    cache = read_news_cache()
    if cache is None or not isinstance(cache.get("items"), list):
        return {"ok": False, "reason": "cache_corrupt"}
    try:
        updated_at = datetime.fromisoformat(cache["updated_at"])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "reason": "cache_corrupt"}
    if updated_at.tzinfo is None:  # naive 타임스탬프는 aware와 뺄셈 불가 → 손상 취급
        return {"ok": False, "reason": "cache_corrupt"}
    age_hours = (datetime.now(UTC) - updated_at).total_seconds() / 3600
    report = {
        "age_hours": round(age_hours, 1),
        "count": len(cache["items"]),
        "sources": cache.get("sources", {}),
    }
    if age_hours > settings.news_max_age_hours:
        return {"ok": False, "reason": "stale", **report}
    if len(cache["items"]) < settings.news_min_items:
        return {"ok": False, "reason": "too_few_items", **report}
    return {"ok": True, **report}
