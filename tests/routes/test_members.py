from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.member import Member
from app.models.member_program import MemberProgram


def test_create_member(client: TestClient, session: Session):
    resp = client.post(
        "/api/members",
        json={"name": "김민준", "email": "minjun@example.com", "program": "협의회"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "김민준"
    assert body["subscribed"] is True
    assert body["id"] is not None

    # program은 member_programs 행으로 기록된다
    mp = session.exec(select(MemberProgram).where(MemberProgram.member_id == body["id"])).one()
    assert mp.program == "협의회"


def test_create_member_duplicate_email_conflict(client: TestClient):
    payload = {"name": "이서연", "email": "seoyeon@example.com"}
    assert client.post("/api/members", json=payload).status_code == 201
    resp = client.post("/api/members", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_list_members_filters_by_program(client: TestClient, session: Session):
    m1 = Member(name="박지훈")
    m2 = Member(name="최하은")
    session.add(m1)
    session.add(m2)
    session.flush()
    assert m1.id is not None and m2.id is not None
    session.add(MemberProgram(member_id=m1.id, program="계약학과"))
    session.add(MemberProgram(member_id=m2.id, program="협의회"))
    session.commit()

    resp = client.get("/api/members", params={"program": "계약학과"})
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "박지훈" in names
    assert "최하은" not in names


def test_get_member_not_found(client: TestClient):
    resp = client.get("/api/members/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
