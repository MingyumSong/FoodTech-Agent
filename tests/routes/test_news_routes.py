from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import settings
from app.services import news


def test_news_refresh_requires_token(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "jobs_token", "test-token")
    assert client.post("/jobs/news-refresh").status_code == 401


def test_news_refresh_accepted_and_runs_in_background(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "jobs_token", "test-token")
    called = {"n": 0}
    monkeypatch.setattr(
        "app.routes.jobs.refresh_news_cache", lambda: called.__setitem__("n", called["n"] + 1)
    )

    resp = client.post("/jobs/news-refresh", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    assert resp.json() == {"job": "news-refresh", "status": "accepted"}
    assert called["n"] == 1  # TestClient는 응답 후 BackgroundTasks를 동기 실행한다


def test_health_news_missing_cache_returns_503(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "news_cache_path", str(tmp_path / "none.json"))
    resp = client.get("/health/news")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "cache_missing"


def test_health_news_ok(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "news_cache_path", str(tmp_path / "news_cache.json"))
    news._write_cache(
        {
            "updated_at": datetime.now(UTC).isoformat(),
            "count": 10,
            "sources": {"domestic": "naver", "overseas": "brave"},
            "items": [{"url": f"https://example.com/{i}"} for i in range(10)],
        }
    )
    resp = client.get("/health/news")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["count"] == 10
