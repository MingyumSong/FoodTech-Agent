"""T-002 스키마 스모크 테스트 — 제약·인덱스가 설계대로 동작하는지 검증."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import EngagementEvent, Member, MemberProgram, Newsletter, SendLog


def _make_campaign(session: Session) -> tuple[Member, Newsletter, SendLog]:
    member = Member(name="테스트회원", email="dup@example.com")
    newsletter = Newsletter(subject="테스트", html_body="<p>hi</p>")
    session.add(member)
    session.add(newsletter)
    session.flush()
    assert member.id is not None and newsletter.id is not None
    log = SendLog(
        newsletter_id=newsletter.id,
        member_id=member.id,
        email="dup@example.com",
        provider_id="resend-msg-1",
    )
    session.add(log)
    session.flush()
    return member, newsletter, log


def test_duplicate_member_email_allowed(session: Session):
    # 실명단에 중복 이메일이 존재 — unique가 아니어야 임포트가 가능하다
    session.add(Member(name="회원A", email="same@example.com"))
    session.add(Member(name="회원B", email="same@example.com"))
    session.flush()


def test_member_program_composite_unique(session: Session):
    member = Member(name="테스트회원")
    session.add(member)
    session.flush()
    assert member.id is not None
    session.add(MemberProgram(member_id=member.id, program="월드푸드테크협의회"))
    session.flush()

    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(MemberProgram(member_id=member.id, program="월드푸드테크협의회"))
            session.flush()

    # 같은 회원이라도 다른 프로그램은 허용 (M:N)
    session.add(MemberProgram(member_id=member.id, program="최고책임자과정", cohort="원우(10기)"))
    session.flush()


def test_send_log_provider_id_unique(session: Session):
    _, newsletter, _ = _make_campaign(session)
    assert newsletter.id is not None
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(
                SendLog(
                    newsletter_id=newsletter.id,
                    email="other@example.com",
                    provider_id="resend-msg-1",
                )
            )
            session.flush()


def test_engagement_event_idempotency_and_payload(session: Session):
    member, newsletter, log = _make_campaign(session)
    assert member.id is not None and newsletter.id is not None and log.id is not None

    event = EngagementEvent(
        send_log_id=log.id,
        member_id=member.id,
        newsletter_id=newsletter.id,
        event_type="clicked",
        url="https://example.com/news/1",
        provider_event_id="evt-1",
        payload={
            "type": "email.clicked",
            "data": {"click": {"link": "https://example.com/news/1"}},
        },
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()

    # jsonb 왕복 확인
    session.refresh(event)
    assert event.payload is not None
    assert event.payload["data"]["click"]["link"] == "https://example.com/news/1"

    # 웹훅 재시도(같은 provider_event_id)는 unique 제약으로 거부 → 멱등
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(
                EngagementEvent(
                    event_type="clicked",
                    provider_event_id="evt-1",
                    occurred_at=datetime.now(UTC),
                )
            )
            session.flush()
