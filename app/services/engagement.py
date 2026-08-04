from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, col, select

from app.lib.logger import get_logger
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.send_log import SendLog

logger = get_logger("engagement")

# Resend 웹훅 타입 → event_type. 목록 밖(email.sent 등)은 무시 (T-003 설계 결정 3)
RESEND_EVENT_TYPES = {
    "email.delivered": "delivered",
    "email.opened": "opened",
    "email.clicked": "clicked",
    "email.bounced": "bounced",
    "email.complained": "complained",
}


def _parse_occurred_at(payload: dict[str, Any]) -> datetime:
    raw = payload.get("created_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed
        except ValueError:
            pass
    return datetime.now(UTC)


def ingest_resend_event(session: Session, provider_event_id: str, payload: dict[str, Any]) -> bool:
    """웹훅 이벤트 1건을 engagement_events에 적재. 적재하면 True, 무시·중복이면 False.

    멱등: provider_event_id(=svix-id) UNIQUE + ON CONFLICT DO NOTHING —
    svix 재시도로 같은 이벤트가 여러 번 와도 1행만 남는다.
    """
    event_type = RESEND_EVENT_TYPES.get(payload.get("type", ""))
    if event_type is None:
        return False

    data = payload.get("data") or {}

    # 발송 로그 역추적: email_id == send_logs.provider_id (T-002 조인 키)
    send_log = None
    email_id = data.get("email_id")
    if email_id:
        send_log = session.exec(select(SendLog).where(SendLog.provider_id == email_id)).first()

    member_id = send_log.member_id if send_log else None
    if member_id is None:
        # 폴백: 수신자 이메일로 회원 매칭. 그것도 없으면 고아 이벤트로 저장 (원본은 보존)
        to = data.get("to")
        recipient = to[0] if isinstance(to, list) and to else None
        if isinstance(recipient, str):
            member = session.exec(select(Member).where(Member.email == recipient)).first()
            member_id = member.id if member else None

    url = None
    if event_type == "clicked":
        click = data.get("click")
        if isinstance(click, dict):
            url = click.get("link")

    stmt = (
        pg_insert(EngagementEvent)
        .values(
            send_log_id=send_log.id if send_log else None,
            member_id=member_id,
            newsletter_id=send_log.newsletter_id if send_log else None,
            event_type=event_type,
            url=url,
            provider_event_id=provider_event_id,
            payload=payload,
            occurred_at=_parse_occurred_at(payload),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["provider_event_id"])
        # ORM insert 경로는 rowcount가 -1이라 신뢰 불가 — RETURNING으로 삽입 여부를 확정한다
        # (conflict로 스킵되면 빈 결과)
        .returning(col(EngagementEvent.id))
    )
    inserted_id = session.execute(stmt).scalar()
    session.commit()
    stored = inserted_id is not None
    if not stored:
        logger.info(f"duplicate webhook event ignored: {provider_event_id}")
    return stored


# 디저트 코너의 원클릭 반응 (T-013). 웹훅이 아니라 우리가 만든 링크로 들어온다.
REACTION_VALUES = {"good", "ok", "bad"}


def record_reaction(session: Session, *, member: Member, newsletter_id: int, value: str) -> None:
    """반응 1건을 engagement_events에 적재. 같은 회원×같은 편은 1행으로 수렴한다.

    멱등 키를 provider_event_id에 직접 만든다(UNIQUE) — 마음이 바뀌어 다시 누르면
    새 행이 쌓이는 게 아니라 마지막 값으로 덮인다. 스키마 변경 없이 event_type + payload로
    해결하려는 설계라 반응값은 payload에 넣는다.
    """
    if value not in REACTION_VALUES:
        raise ValueError(f"unknown reaction: {value}")

    now = datetime.now(UTC)
    key = f"reaction:{member.id}:{newsletter_id}"
    payload = {"reaction": value, "newsletter_id": newsletter_id}
    stmt = (
        pg_insert(EngagementEvent)
        .values(
            member_id=member.id,
            newsletter_id=newsletter_id,
            event_type="reacted",
            provider_event_id=key,
            payload=payload,
            occurred_at=now,
            created_at=now,
        )
        .on_conflict_do_update(
            index_elements=["provider_event_id"],
            set_={"payload": payload, "occurred_at": now},
        )
    )
    session.execute(stmt)
    session.commit()
    logger.info(f"reaction recorded: member_id={member.id} nl={newsletter_id} value={value}")
