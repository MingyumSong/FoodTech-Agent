"""점수 전용 토큰 — 대시보드 연동에 관리자 비번을 통째로 넘기지 않기 위한 분리."""

import base64

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.models.member import Member
from app.models.pilot_member import PilotMember

ADMIN = "admin-secret"
SCORES = "scores-only-secret"


def _auth(password: str) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _pilot(session: Session) -> None:
    m = Member(name="김참여", email="who@example.com", subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    session.add(PilotMember(member_id=m.id, name=m.name))  # pyright: ignore[reportArgumentType]
    session.commit()


def _both(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_token", ADMIN)
    monkeypatch.setattr(settings, "scores_token", SCORES)
    monkeypatch.setattr(settings, "app_env", "prod")


def test_scores_token_opens_only_the_csv(client: TestClient, monkeypatch):
    """이 토큰으로는 CSV만 열린다 — 회원 명단도, 발송도 못 연다.

    지금까지 대시보드에 넘어가 있던 관리자 비번은 이 셋을 **전부** 열었다.
    """
    _both(monkeypatch)
    h = _auth(SCORES)
    assert client.get("/admin/scores.csv", headers=h).status_code == 200
    assert client.get("/admin/api/members", headers=h).status_code == 401
    assert client.get("/admin/members", headers=h).status_code == 401
    assert client.post("/admin/api/review/send", headers=h).status_code == 401
    assert client.get("/admin/dashboard", headers=h).status_code == 401


def test_scores_token_gets_no_email(client: TestClient, session: Session, monkeypatch):
    """대시보드는 순위만 보여준다 — 연락처는 애초에 내보내지 않는다."""
    _both(monkeypatch)
    _pilot(session)

    limited = client.get("/admin/scores.csv", headers=_auth(SCORES)).text
    assert "김참여" in limited
    assert "who@example.com" not in limited
    assert "이메일" not in limited  # 열 자체가 없다


def test_admin_password_still_gets_everything(client: TestClient, session: Session, monkeypatch):
    """사람이 내려받는 명단은 그대로 — 행사·베네핏 대상을 고르려면 연락처가 필요하다."""
    _both(monkeypatch)
    _pilot(session)

    full = client.get("/admin/scores.csv", headers=_auth(ADMIN)).text
    assert "who@example.com" in full and "이메일" in full


def test_wrong_and_missing_credentials_are_rejected(client: TestClient, monkeypatch):
    _both(monkeypatch)
    assert client.get("/admin/scores.csv").status_code == 401
    assert client.get("/admin/scores.csv", headers=_auth("nope")).status_code == 401


def test_scores_token_unset_means_admin_only(client: TestClient, monkeypatch):
    """토큰을 안 넣으면 이 경로는 아예 없다 — 빈 문자열이 통과 조건이 되면 안 된다."""
    monkeypatch.setattr(settings, "admin_token", ADMIN)
    monkeypatch.setattr(settings, "scores_token", "")
    monkeypatch.setattr(settings, "app_env", "prod")

    assert client.get("/admin/scores.csv", headers=_auth("")).status_code == 401
    assert client.get("/admin/scores.csv", headers=_auth(ADMIN)).status_code == 200
