from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.member import Member


def _member(session: Session, token: str = "tok-unsub") -> Member:
    m = Member(name="테스터", email="unsub@example.com", subscribed=True, unsubscribe_token=token)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def test_unsubscribe_get_only_asks(client: TestClient, session: Session):
    """GET은 확인 페이지만 — 링크를 여는 것만으로 해지되면 안 된다 (T-025).

    메일 클라이언트·보안 게이트웨이의 링크 프리페치가 이 GET을 대신 눌러버릴 수 있고,
    그렇게 끊긴 구독은 본인이 알지도 못한 채 되돌릴 방법이 없다.
    """
    m = _member(session)
    resp = client.get("/unsubscribe/tok-unsub")
    assert resp.status_code == 200
    assert "수신거부 하시겠어요" in resp.text
    assert 'action="/unsubscribe/tok-unsub"' in resp.text  # 확인 버튼이 POST로 간다
    session.refresh(m)
    assert m.subscribed is True  # ← 핵심: 아무것도 안 바뀌었다


def test_unsubscribe_post_one_click(client: TestClient, session: Session):
    """RFC 8058 one-click — Gmail이 POST로 자동 호출한다. 확인 페이지 버튼도 같은 경로다."""
    m = _member(session, token="tok-oneclick")
    resp = client.post("/unsubscribe/tok-oneclick")
    assert resp.status_code == 200
    assert "수신거부가 완료" in resp.text
    session.refresh(m)
    assert m.subscribed is False

    # 재호출도 성공 (멱등)
    assert client.post("/unsubscribe/tok-oneclick").status_code == 200


def test_unsubscribe_get_after_done_shows_result(client: TestClient, session: Session):
    """이미 해지된 사람에게 "수신거부 하시겠어요?"를 다시 묻지 않는다."""
    m = _member(session, token="tok-already")
    m.subscribed = False
    session.add(m)
    session.commit()
    resp = client.get("/unsubscribe/tok-already")
    assert resp.status_code == 200
    assert "수신거부가 완료" in resp.text


def test_unsubscribe_unknown_token_404(client: TestClient):
    assert client.get("/unsubscribe/no-such-token").status_code == 404
    assert client.post("/unsubscribe/no-such-token").status_code == 404


def test_unsubscribe_stamps_updated_at(client: TestClient, session: Session):
    """언제 끊겼는지가 남아야 한다 — 예전엔 subscribed만 바뀌고 updated_at은 그대로였다."""
    m = _member(session, token="tok-stamp")
    before = m.updated_at
    client.post("/unsubscribe/tok-stamp")
    session.refresh(m)
    assert m.updated_at > before
