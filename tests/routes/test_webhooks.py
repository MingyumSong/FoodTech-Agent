import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.newsletter import Newsletter
from app.models.send_log import SendLog

SECRET_KEY = b"0123456789abcdef0123456789abcdef"
TEST_SECRET = "whsec_" + base64.b64encode(SECRET_KEY).decode()


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", TEST_SECRET)


def _headers(body: bytes, *, svix_id: str = "msg_test_1", ts: str | None = None) -> dict[str, str]:
    ts = str(int(time.time())) if ts is None else ts
    signed = f"{svix_id}.{ts}.".encode() + body
    sig = base64.b64encode(hmac.new(SECRET_KEY, signed, hashlib.sha256).digest()).decode()
    return {"svix-id": svix_id, "svix-timestamp": ts, "svix-signature": f"v1,{sig}"}


def _clicked_payload(
    email_id: str = "re_msg_1",
    link: str = "https://example.com/news/1",
    to: str = "user@example.com",
) -> dict:
    return {
        "type": "email.clicked",
        "created_at": "2026-07-18T09:00:00.000Z",
        "data": {
            "email_id": email_id,
            "to": [to],
            "click": {"link": link, "userAgent": "test-ua", "ipAddress": "1.2.3.4"},
        },
    }


def _events(session: Session) -> list[EngagementEvent]:
    return list(session.exec(select(EngagementEvent)).all())


def test_clicked_event_resolves_send_log(client: TestClient, session: Session):
    member = Member(name="김민준", email="user@example.com")
    newsletter = Newsletter(subject="푸디픽 #1", html_body="<p>hi</p>")
    session.add(member)
    session.add(newsletter)
    session.flush()
    assert member.id is not None and newsletter.id is not None
    send_log = SendLog(
        newsletter_id=newsletter.id,
        member_id=member.id,
        email="user@example.com",
        status="sent",
        provider_id="re_msg_1",
    )
    session.add(send_log)
    session.commit()

    body = json.dumps(_clicked_payload()).encode()
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "stored": True}

    (event,) = _events(session)
    assert event.event_type == "clicked"
    assert event.url == "https://example.com/news/1"
    assert event.member_id == member.id
    assert event.newsletter_id == newsletter.id
    assert event.send_log_id == send_log.id
    assert event.provider_event_id == "msg_test_1"
    assert event.payload is not None and event.payload["type"] == "email.clicked"
    assert event.occurred_at == datetime(2026, 7, 18, 9, 0, tzinfo=UTC)


def test_duplicate_svix_id_is_idempotent(client: TestClient, session: Session):
    body = json.dumps(_clicked_payload()).encode()
    headers = _headers(body)
    assert client.post("/webhooks/resend", content=body, headers=headers).json()["stored"] is True
    assert client.post("/webhooks/resend", content=body, headers=headers).json()["stored"] is False
    assert len(_events(session)) == 1


def test_tampered_body_rejected(client: TestClient, session: Session):
    body = json.dumps(_clicked_payload()).encode()
    headers = _headers(body)
    tampered = body.replace(b"news/1", b"news/2")
    resp = client.post("/webhooks/resend", content=tampered, headers=headers)
    assert resp.status_code == 401
    assert len(_events(session)) == 0


def test_missing_signature_headers_rejected(client: TestClient, session: Session):
    body = json.dumps(_clicked_payload()).encode()
    resp = client.post("/webhooks/resend", content=body)
    assert resp.status_code == 401
    assert len(_events(session)) == 0


def test_unconfigured_secret_returns_503(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "resend_webhook_secret", "")
    body = json.dumps(_clicked_payload()).encode()
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body))
    assert resp.status_code == 503


def test_stale_timestamp_rejected(client: TestClient, session: Session):
    body = json.dumps(_clicked_payload()).encode()
    stale = str(int(time.time()) - 3600)
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body, ts=stale))
    assert resp.status_code == 401
    assert len(_events(session)) == 0


def test_ignored_event_type_returns_200_without_storing(client: TestClient, session: Session):
    payload = {"type": "email.sent", "created_at": "2026-07-18T09:00:00.000Z", "data": {}}
    body = json.dumps(payload).encode()
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body))
    assert resp.status_code == 200
    assert resp.json()["stored"] is False
    assert len(_events(session)) == 0


def test_orphan_event_still_stored(client: TestClient, session: Session):
    # send_log도 회원도 못 찾는 이벤트 — FK 없이라도 원본은 보존한다
    body = json.dumps(_clicked_payload(email_id="re_unknown", to="ghost@example.com")).encode()
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body))
    assert resp.status_code == 200
    (event,) = _events(session)
    assert event.member_id is None
    assert event.newsletter_id is None
    assert event.send_log_id is None


def test_member_fallback_by_recipient_email(client: TestClient, session: Session):
    member = Member(name="이서연", email="fallback@example.com")
    session.add(member)
    session.commit()

    body = json.dumps(_clicked_payload(email_id="re_unknown", to="fallback@example.com")).encode()
    client.post("/webhooks/resend", content=body, headers=_headers(body))
    (event,) = _events(session)
    assert event.member_id == member.id
    assert event.newsletter_id is None


def test_invalid_json_with_valid_signature_returns_400(client: TestClient):
    body = b"not-json"
    resp = client.post("/webhooks/resend", content=body, headers=_headers(body))
    assert resp.status_code == 400
