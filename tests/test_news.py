import json
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import settings
from app.lib.http import get_with_retry
from app.services import news
from app.services.news_sources import SEARCH_QUERIES

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>feed</title>
<item>
  <title>Cultivated meat startup raises $10M</title>
  <link>https://example.com/articles/1</link>
  <description>A foodtech startup...</description>
  <pubDate>Mon, 13 Jul 2026 09:00:00 +0900</pubDate>
</item>
<item>
  <title>&lt;b&gt;푸드테크&lt;/b&gt; 스마트팩토리 확산</title>
  <link>https://example.com/articles/2</link>
  <description>식품 제조 자동화...</description>
  <pubDate>Sun, 12 Jul 2026 09:00:00 +0900</pubDate>
</item>
</channel></rss>""".encode()


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_llm_classification(monkeypatch):
    # refresh_news_cache가 T-006 분류를 타지 않게 — 분류 자체는 test_news_classify.py에서 검증
    monkeypatch.setattr(settings, "openrouter_api_key", "")


@pytest.fixture
def cache_path(tmp_path, monkeypatch):
    path = tmp_path / "news_cache.json"
    monkeypatch.setattr(settings, "news_cache_path", str(path))
    return path


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


# ---------------------------------------------------------------- retry (AC2)


def test_retry_succeeds_after_transient_errors():
    statuses = iter([429, 500, 200])
    calls = {"n": 0}
    sleeps: list[float] = []

    def handler(request):
        calls["n"] += 1
        return httpx.Response(next(statuses))

    resp = get_with_retry(
        "https://api.example.com/x",
        client=make_client(handler),
        backoff_base=1.0,
        sleep=sleeps.append,
    )
    assert resp.status_code == 200
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]  # 지수 백오프


def test_retry_gives_up_after_max_attempts():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError):
        get_with_retry(
            "https://api.example.com/x",
            client=make_client(handler),
            max_attempts=3,
            sleep=lambda _s: None,
        )
    assert calls["n"] == 3


def test_retry_does_not_retry_permanent_errors():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        get_with_retry("https://api.example.com/x", client=make_client(handler))
    assert calls["n"] == 1


def test_retry_on_timeout():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectTimeout("timeout")
        return httpx.Response(200)

    resp = get_with_retry(
        "https://api.example.com/x", client=make_client(handler), sleep=lambda _s: None
    )
    assert resp.status_code == 200
    assert calls["n"] == 2


# ---------------------------------------------------------------- fallback (AC1)


def test_brave_error_falls_back_to_rss_even_with_key(cache_path, no_sleep, monkeypatch):
    """키가 있어도 Brave가 오류를 반환하면 해외 RSS 폴백이 동작해야 한다 (프로토타입 결함)."""
    monkeypatch.setattr(settings, "brave_search_api_key", "some-key")
    monkeypatch.setattr(settings, "naver_client_id", "")
    monkeypatch.setattr(settings, "naver_client_secret", "")
    brave_calls = {"n": 0}

    def handler(request):
        if request.url.host == "api.search.brave.com":
            brave_calls["n"] += 1
            return httpx.Response(429)  # 한도초과 시나리오
        return httpx.Response(200, content=RSS_XML)

    cache = news.refresh_news_cache(client=make_client(handler))

    assert brave_calls["n"] > 0  # 키가 있으니 Brave를 시도는 했고
    assert cache["sources"]["overseas"] == "rss"  # 실패하자 RSS로 폴백했다
    assert cache["sources"]["domestic"] == "rss"  # 네이버 키 없음 → 국내도 RSS
    assert cache["count"] > 0
    assert any(it["url"] == "https://example.com/articles/1" for it in cache["items"])
    assert json.loads(cache_path.read_text(encoding="utf-8"))["count"] == cache["count"]


def test_primary_sources_used_when_healthy(cache_path, monkeypatch):
    item_naver = {
        "title": "t",
        "url": "https://n.example.com/1",
        "summary": "",
        "source": "",
        "published_at": "",
        "category": "일반",
        "origin": "naver",
        "region": "domestic",
    }
    item_brave = {**item_naver, "url": "https://b.example.com/1", "origin": "brave"}
    monkeypatch.setattr(news, "fetch_naver", lambda client=None: [item_naver])
    monkeypatch.setattr(news, "fetch_brave", lambda client=None, sleep=None: [item_brave])
    monkeypatch.setattr(
        news,
        "fetch_rss_pool",
        lambda *a, **k: pytest.fail("1차 소스가 정상인데 RSS 폴백을 호출했다"),
    )

    cache = news.refresh_news_cache()
    assert cache["sources"] == {"domestic": "naver", "overseas": "brave"}
    assert cache["count"] == 2


def test_naver_parses_and_shares_queries(cache_path, monkeypatch):
    """네이버 경로가 공용 쿼리 목록을 그대로 사용하고, 니치 검색어는 sim 병행 수집한다 (AC4)."""
    monkeypatch.setattr(settings, "naver_client_id", "id")
    monkeypatch.setattr(settings, "naver_client_secret", "secret")
    seen: list[tuple[str, str]] = []

    def handler(request):
        assert request.url.host == "openapi.naver.com"
        seen.append((request.url.params["query"], request.url.params["sort"]))
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "<b>배양육</b> 상용화 임박",
                        "originallink": "https://media.example.com/1",
                        "link": "https://news.naver.com/1",
                        "description": "요약 <b>텍스트</b>",
                        "pubDate": "Mon, 13 Jul 2026 10:00:00 +0900",
                    }
                ]
            },
        )

    items = news.fetch_naver(client=make_client(handler))
    expected = [
        (q.ko, sort)
        for q in SEARCH_QUERIES
        for sort in (("date", "sim") if q.naver_sim else ("date",))
    ]
    assert seen == expected
    assert sum(1 for _, sort in seen if sort == "sim") == 3  # 니치 3종만 병행
    assert items[0]["title"] == "배양육 상용화 임박"  # HTML 태그 제거
    assert items[0]["url"] == "https://media.example.com/1"  # 언론사 원문 우선
    assert items[0]["published_at"].startswith("2026-07-13")


# ---------------------------------------------------------------- healthcheck (AC3)


def _write_cache_with(items_count: int, age_hours: float = 0.0) -> None:
    news._write_cache(
        {
            "updated_at": (datetime.now(UTC) - timedelta(hours=age_hours)).isoformat(),
            "count": items_count,
            "sources": {"domestic": "naver", "overseas": "brave"},
            "items": [{"url": f"https://example.com/{i}"} for i in range(items_count)],
        }
    )


def test_health_missing_cache(cache_path):
    assert news.check_news_health() == {"ok": False, "reason": "cache_missing"}


def test_health_corrupt_cache(cache_path):
    cache_path.write_text("not json at all", encoding="utf-8")
    assert news.check_news_health()["reason"] == "cache_corrupt"


@pytest.mark.parametrize(
    "payload",
    [
        {"updated_at": "2026-07-13T10:00:00", "items": [{}] * 10},  # naive 타임스탬프
        {"updated_at": 1720000000, "items": [{}] * 10},  # 문자열 아닌 타임스탬프
        {"updated_at": "2026-07-13T10:00:00+00:00", "items": None},  # items가 null
        {"updated_at": "2026-07-13T10:00:00+00:00", "items": "aaaaaaaaaa"},  # items가 문자열
        {"items": [{}] * 10},  # updated_at 누락
    ],
)
def test_health_malformed_cache_is_corrupt_not_crash(cache_path, payload):
    """형식이 깨진 캐시는 500 크래시나 거짓 OK가 아니라 cache_corrupt 신호여야 한다."""
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    assert news.check_news_health() == {"ok": False, "reason": "cache_corrupt"}


def test_health_ok(cache_path):
    _write_cache_with(items_count=10)
    report = news.check_news_health()
    assert report["ok"] is True
    assert report["count"] == 10


def test_health_stale(cache_path):
    _write_cache_with(items_count=10, age_hours=settings.news_max_age_hours + 1)
    report = news.check_news_health()
    assert report["ok"] is False
    assert report["reason"] == "stale"


def test_health_too_few_items(cache_path):
    _write_cache_with(items_count=settings.news_min_items - 1)
    report = news.check_news_health()
    assert report["ok"] is False
    assert report["reason"] == "too_few_items"
