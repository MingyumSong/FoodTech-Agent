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
    monkeypatch.setattr(settings, "admin_token", "")
    resp = client.get("/admin/status", headers=_auth("anything"))
    assert resp.status_code == 503


def test_status_renders_stats_without_pii(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "secret-token")
    _seed(session)
    resp = client.get("/admin/status", headers=_auth("secret-token"))
    assert resp.status_code == 200
    assert "파이프라인 현황" in resp.text
    assert "pilot-lab" in resp.text  # 프로그램 집계는 표시
    assert "t@example.com" not in resp.text  # PII 금지 (C6)
    assert "테스터" not in resp.text
