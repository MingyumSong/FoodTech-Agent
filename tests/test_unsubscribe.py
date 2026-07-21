from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.member import Member


def _member(session: Session, token: str = "tok-unsub") -> Member:
    m = Member(name="테스터", email="unsub@example.com", subscribed=True, unsubscribe_token=token)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def test_unsubscribe_get_flips_subscribed(client: TestClient, session: Session):
    m = _member(session)
    resp = client.get("/unsubscribe/tok-unsub")
    assert resp.status_code == 200
    assert "수신거부가 완료" in resp.text
    session.refresh(m)
    assert m.subscribed is False

    # 재클릭도 성공 (멱등)
    assert client.get("/unsubscribe/tok-unsub").status_code == 200


def test_unsubscribe_post_one_click(client: TestClient, session: Session):
    """RFC 8058 one-click — Gmail이 POST로 자동 호출한다."""
    m = _member(session, token="tok-oneclick")
    resp = client.post("/unsubscribe/tok-oneclick")
    assert resp.status_code == 200
    session.refresh(m)
    assert m.subscribed is False


def test_unsubscribe_unknown_token_404(client: TestClient):
    assert client.get("/unsubscribe/no-such-token").status_code == 404
