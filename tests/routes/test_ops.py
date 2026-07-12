from fastapi.testclient import TestClient


def test_health_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


def test_jobs_ping_requires_token(client: TestClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "jobs_token", "test-token")

    assert client.post("/jobs/ping").status_code == 401
    resp = client.post("/jobs/ping", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_jobs_ping_unconfigured_returns_503(client: TestClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "jobs_token", "")
    assert client.post("/jobs/ping").status_code == 503
