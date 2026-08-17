"""T-027 4단계 — 개발 모드. 랩실이 시크릿 없이 화면을 볼 수 있게 하되, 운영은 절대 안 열린다."""

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings

TOKEN = "secret-token"


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.mark.parametrize(
    ("app_env", "admin_token", "expected"),
    [
        ("local", "", True),  # 새로 클론한 랩실 개발자
        ("dev", "", True),
        ("test", "", True),
        ("prod", "", False),  # ★ 운영에서 토큰이 사라져도 열리지 않는다
        ("local", "x", False),  # 토큰이 있으면 개발 환경이라도 잠근다
        ("prod", "x", False),  # 정상 운영
        ("staging", "", False),  # 모르는 환경값은 닫히는 쪽으로
        ("", "", False),
    ],
)
def test_dev_mode_fails_closed(app_env: str, admin_token: str, expected: bool):
    """두 조건이 모두 맞을 때만 열린다. 운영은 APP_ENV=prod 를 명시적으로 넣는다."""
    assert Settings(app_env=app_env, admin_token=admin_token).dev_mode is expected


def test_dashboard_opens_without_credentials_in_dev(client: TestClient, monkeypatch):
    """랩실 개발자가 클론 직후 화면을 볼 수 있어야 한다 — 없으면 거기서 막힌다."""
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "app_env", "local")

    res = client.get("/admin/dashboard")
    assert res.status_code == 200
    assert "World FoodTech Database" in res.text
    assert "개발 모드" in res.text  # 인증이 꺼진 걸 숨기지 않는다


def test_dev_banner_is_absent_when_locked(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "app_env", "prod")

    res = client.get("/admin/dashboard", headers=_auth())
    assert res.status_code == 200
    assert "개발 모드" not in res.text
    assert "dev-banner" not in res.text


def test_production_without_token_is_still_locked(client: TestClient, monkeypatch):
    """운영에서 ADMIN_TOKEN 이 유실돼도 회원 명단이 열리면 안 된다 — 503으로 죽는 게 맞다."""
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "app_env", "prod")

    assert client.get("/admin/dashboard").status_code == 503
    assert client.get("/admin/api/members").status_code == 503
    assert client.post("/admin/api/review/send").status_code == 503


def test_data_apis_open_in_dev_too(client: TestClient, monkeypatch):
    """셸만 열리고 데이터가 401이면 화면이 에러투성이라 개발을 못 한다."""
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "app_env", "local")

    assert client.get("/admin/api/newsletter").status_code == 200
    assert client.get("/admin/api/members").status_code == 200
    assert client.get("/admin/api/review").status_code == 200
