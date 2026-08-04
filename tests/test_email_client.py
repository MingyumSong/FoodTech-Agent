"""Resend payload 조립 검증 (T-013).

발신 도메인 news.foodtech-center.org에는 MX가 없다 — reply_to가 빠지면 수신자의 답장이
반송된다. 푸터가 "답장하시면 운영진에게 전달됩니다"라고 약속하므로 이 헤더는 계약이다.
"""

from typing import Any

import pytest

from app.config import settings
from app.lib.email_client import send_email


class _FakeResponse:
    status_code = 200

    def json(self) -> dict[str, str]:
        return {"id": "resend-fake-id"}

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    """post 호출의 payload를 잡아두는 httpx.Client 대역."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: int):
        self.payloads.append(json)
        return _FakeResponse()


@pytest.fixture
def client() -> _FakeClient:
    return _FakeClient()


def _send(client: _FakeClient) -> str | None:
    return send_email(
        client,  # pyright: ignore[reportArgumentType]
        to="reader@example.com",
        subject="푸디픽 #013",
        html="<p>본문</p>",
    )


def test_reply_to_is_sent_when_configured(client: _FakeClient, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "newsletter_reply_to", "ops@example.com")

    assert _send(client) == "resend-fake-id"
    assert client.payloads[0]["reply_to"] == "ops@example.com"


def test_reply_to_omitted_when_blank(client: _FakeClient, monkeypatch):
    """미설정이면 키 자체를 넣지 않는다 — 빈 문자열을 보내면 Resend가 거절한다."""
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "newsletter_reply_to", "")

    assert _send(client) == "resend-fake-id"
    assert "reply_to" not in client.payloads[0]


def test_dry_run_sends_nothing(client: _FakeClient, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "newsletter_reply_to", "ops@example.com")

    assert _send(client) is None
    assert client.payloads == []
