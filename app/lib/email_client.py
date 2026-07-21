"""Resend 발송 클라이언트 (T-008).

- 키가 없으면 DRY RUN: 실발송 없이 None을 반환한다 (프로토타입 검증 패턴 재작성, C5).
- 반환값 = Resend email_id. send_logs.provider_id로 저장돼 웹훅 이벤트 역추적의 조인 키가 된다.
- 호출부(서비스)가 발송 간격을 조절한다 — Resend rate limit 2 req/s.
"""

import time

import httpx

from app.config import settings
from app.lib.logger import get_logger

logger = get_logger("email_client")

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(
    client: httpx.Client,
    *,
    to: str,
    subject: str,
    html: str,
    headers: dict[str, str] | None = None,
) -> str | None:
    """1통 발송 — Resend email_id 반환. DRY RUN이면 None.

    일시 오류(429/5xx)는 3회 재시도, 최종 실패는 예외 전파(호출부가 수신자 단위로 격리).
    """
    if not settings.resend_api_key:
        logger.info("DRY RUN: no RESEND_API_KEY, skipping actual send")
        return None

    payload: dict[str, object] = {
        "from": settings.newsletter_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if headers:
        payload["headers"] = headers

    resp = None
    for attempt in range(3):
        resp = client.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=30,
        )
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
        return resp.json()["id"]
    assert resp is not None
    resp.raise_for_status()
    return None
