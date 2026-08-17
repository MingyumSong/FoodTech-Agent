import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem


def _auth(password: str) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _seed(session: Session) -> None:
    m = Member(name="테스터", email="t@example.com", subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    session.add(MemberProgram(member_id=m.id, program="pilot-lab"))  # pyright: ignore[reportArgumentType]
    session.add(
        NewsItem(
            title="현황판 테스트 뉴스",
            url="https://news.example.com/status",
            summary="요약",
            source="테스트일보",
            origin="naver",
            region="domestic",
            category="general",
            published_at=datetime.now(UTC),
            collected_at=datetime.now(UTC),
        )
    )
    session.commit()


def test_status_requires_basic_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "secret-token")
    assert client.get("/admin/status").status_code == 401
    assert client.get("/admin/status", headers=_auth("wrong")).status_code == 401


def test_status_unconfigured_returns_503(client: TestClient, monkeypatch):
    """토큰이 없으면 503 — 단 **운영 환경일 때**다 (T-027 4단계로 조건이 날카로워졌다).

    예전엔 "토큰 없음 = 무조건 503"이었다. 지금은 개발 환경(APP_ENV=local 등)에서
    토큰이 없으면 개발 모드로 열린다 — 랩실이 시크릿 없이 화면을 볼 수 있게.
    운영은 APP_ENV=prod 라 예전 그대로 닫힌다.
    """
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "app_env", "prod")
    resp = client.get("/admin/status", headers=_auth("anything"))
    assert resp.status_code == 503


def test_status_opens_in_dev_mode(client: TestClient, monkeypatch):
    """같은 조건이라도 개발 환경이면 열린다 — 위 테스트와 짝이다."""
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "app_env", "local")
    assert client.get("/admin/status").status_code == 200


def test_status_renders_stats_without_pii(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "secret-token")
    _seed(session)
    resp = client.get("/admin/status", headers=_auth("secret-token"))
    assert resp.status_code == 200
    assert "파이프라인 현황" in resp.text
    assert "pilot-lab" in resp.text  # 프로그램 집계는 표시
    assert "t@example.com" not in resp.text  # PII 금지 (C6)
    assert "테스터" not in resp.text
