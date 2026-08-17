"""T-027 3a — 회원 관리 모달의 JSON API. 목록·발송대상 토글·구독·삭제."""

import base64

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models.member import Member
from app.models.member_program import MemberProgram

TOKEN = "secret-token"
PILOT = "pilot-daily"


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _member(session: Session, name: str, email: str, *, program: str | None = None) -> Member:
    m = Member(name=name, email=email, subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    if program:
        session.add(MemberProgram(member_id=m.id, program=program))  # pyright: ignore[reportArgumentType]
        session.commit()
    return m


def test_list_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/api/members").status_code == 401


def test_list_marks_who_is_on_the_send_list(client: TestClient, session: Session, monkeypatch):
    """화면이 '발송 대상 / 대상 아님'을 그리려면 이 플래그가 정확해야 한다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _member(session, "받는사람", "in@example.com", program=PILOT)
    _member(session, "안받는사람", "out@example.com", program="월드푸드테크협의회")

    rows = {
        m["name"]: m for m in client.get("/admin/api/members", headers=_auth()).json()["members"]
    }
    assert rows["받는사람"]["in_pilot"] is True
    assert rows["안받는사람"]["in_pilot"] is False
    assert rows["안받는사람"]["programs"] == ["월드푸드테크협의회"]


def test_can_add_existing_member_to_send_list(client: TestClient, session: Session, monkeypatch):
    """지금까지 관리자 화면에 **없던** 기능 (T-027 3a).

    2026-08-17에 교수님을 pilot-daily에 넣어달라는 요청이 왔는데, 회원은 이미 있고
    구독중인데도 프로그램에 넣을 방법이 UI에 없어 스크립트를 돌려야 했다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "기존회원", "prof@example.com", program="월드푸드테크협의회")

    res = client.post(
        f"/admin/api/members/{m.id}/program",
        json={"program": PILOT, "joined": True},
        headers=_auth(),
    )
    assert res.status_code == 200 and res.json()["changed"] is True

    links = session.exec(select(MemberProgram.program).where(MemberProgram.member_id == m.id)).all()
    assert PILOT in links

    # 멱등: 두 번 넣어도 행이 늘지 않는다
    again = client.post(
        f"/admin/api/members/{m.id}/program",
        json={"program": PILOT, "joined": True},
        headers=_auth(),
    )
    assert again.json()["changed"] is False
    rows = session.exec(
        select(MemberProgram).where(MemberProgram.member_id == m.id, MemberProgram.program == PILOT)
    ).all()
    assert len(rows) == 1


def test_can_remove_from_send_list(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "빼는회원", "off@example.com", program=PILOT)

    res = client.post(
        f"/admin/api/members/{m.id}/program",
        json={"program": PILOT, "joined": False},
        headers=_auth(),
    )
    assert res.json()["changed"] is True
    links = session.exec(select(MemberProgram.program).where(MemberProgram.member_id == m.id)).all()
    assert PILOT not in links


def test_program_toggle_does_not_touch_subscription(
    client: TestClient, session: Session, monkeypatch
):
    """프로그램과 구독은 뜻이 다르다 — 발송 대상에서 빼는 게 수신거부는 아니다.

    둘을 묶으면 "이번 호만 빼자"가 수신동의 철회로 기록된다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "구독유지", "keep@example.com", program=PILOT)
    client.post(
        f"/admin/api/members/{m.id}/program",
        json={"program": PILOT, "joined": False},
        headers=_auth(),
    )
    session.refresh(m)
    assert m.subscribed is True


def test_subscription_toggle_and_delete(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "토글대상", "t@example.com", program=PILOT)

    off = client.post(
        f"/admin/api/members/{m.id}/subscribed", json={"subscribed": False}, headers=_auth()
    )
    assert off.json() == {"changed": True, "subscribed": False}
    # 같은 값으로 다시 → 아무 일도 없다(이탈 시점 기록이 흔들리면 안 된다)
    same = client.post(
        f"/admin/api/members/{m.id}/subscribed", json={"subscribed": False}, headers=_auth()
    )
    assert same.json()["changed"] is False

    assert client.delete(f"/admin/api/members/{m.id}", headers=_auth()).status_code == 200
    assert session.get(Member, m.id) is None


def test_unknown_member_is_404_not_500(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert (
        client.post(
            "/admin/api/members/999999/program",
            json={"program": PILOT, "joined": True},
            headers=_auth(),
        ).status_code
        == 404
    )
    assert client.delete("/admin/api/members/999999", headers=_auth()).status_code == 404


def test_create_rejects_duplicate_email(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _member(session, "먼저", "dup@example.com")
    res = client.post(
        "/admin/api/members", json={"name": "나중", "email": "dup@example.com"}, headers=_auth()
    )
    assert res.status_code == 409
