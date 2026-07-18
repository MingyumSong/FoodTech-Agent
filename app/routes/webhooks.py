import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.lib.logger import get_logger
from app.lib.webhook import verify_svix_signature
from app.services.engagement import ingest_resend_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger("webhooks")


@router.post("/resend")
async def resend_webhook(
    request: Request,
    session: Session = Depends(get_session),
    svix_id: str = Header(default="", alias="svix-id"),
    svix_timestamp: str = Header(default="", alias="svix-timestamp"),
    svix_signature: str = Header(default="", alias="svix-signature"),
) -> dict[str, bool]:
    """Resend 참여 이벤트(open/click/bounce 등) 수신 — 인증은 svix 서명 검증.

    비 2xx를 반환하면 svix가 재시도하므로, 무시 대상 이벤트도 200으로 답한다.
    """
    if not settings.resend_webhook_secret:
        raise HTTPException(status_code=503, detail="RESEND_WEBHOOK_SECRET not configured")

    body = await request.body()
    if not verify_svix_signature(
        settings.resend_webhook_secret, svix_id, svix_timestamp, svix_signature, body
    ):
        logger.warning("webhook signature verification failed")
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid JSON body") from None

    stored = ingest_resend_event(session, svix_id, payload)
    return {"ok": True, "stored": stored}
