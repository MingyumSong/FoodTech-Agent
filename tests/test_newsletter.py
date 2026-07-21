from datetime import UTC, datetime

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.send_log import SendLog
from app.services import newsletter as nl_service
from app.services.newsletter import (
    PILOT_MAX_RECIPIENTS,
    UNSUB_PLACEHOLDER,
    build_newsletter,
    send_newsletter,
)

PROGRAM = "pilot-lab"
LONG_SUMMARY = "배양육 기술의 상용화가 빨라지고 있다. " * 5  # 60자 이상 (메인 코너 조건)


def _seed_news(session: Session, n: int = 6) -> None:
    now = datetime.now(UTC)
    for i in range(n):
        session.add(
            NewsItem(
                title=f"테스트 뉴스 {i}",
                url=f"https://news.example.com/{i}",
                summary=LONG_SUMMARY if i < 3 else "짧은 요약",
                source="테스트일보",
                origin="naver",
                region="domestic",
                category="cell_cultured",
                published_at=now,
                collected_at=now,
            )
        )
    session.commit()


def _seed_members(session: Session, n: int = 3, *, subscribed: bool = True) -> list[Member]:
    members = []
    for i in range(n):
        m = Member(
            name=f"테스터{i}",
            email=f"tester{i}@example.com",
            subscribed=subscribed,
            unsubscribe_token=f"tok-{i}",
        )
        session.add(m)
        session.commit()
        session.refresh(m)
        session.add(MemberProgram(member_id=m.id, program=PROGRAM))  # pyright: ignore[reportArgumentType]
        members.append(m)
    session.commit()
    return members


def test_build_assembles_draft_and_is_idempotent_same_day(session: Session):
    _seed_news(session)
    nl = build_newsletter(session, program=PROGRAM)
    assert nl.status == "draft"
    assert "푸디픽" in nl.subject
    assert "테스트 뉴스 0" in nl.html_body
    assert UNSUB_PLACEHOLDER in nl.html_body  # 수신자별 치환 전 플레이스홀더
    assert "https://news.example.com/0" in nl.html_body  # 원본 URL 그대로 (클릭 매칭 전제)

    again = build_newsletter(session, program=PROGRAM)
    assert again.id == nl.id  # 같은 날 같은 세그먼트 → 재사용


def test_build_fails_without_enough_news(session: Session):
    with pytest.raises(ValueError, match="최소"):
        build_newsletter(session, program=PROGRAM)


def test_send_dry_run_logs_and_idempotent(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    _seed_news(session)
    _seed_members(session, 3)
    nl = build_newsletter(session, program=PROGRAM)

    stats = send_newsletter(nl.id, session=session)  # pyright: ignore[reportArgumentType]
    assert stats == {
        "newsletter_id": nl.id,
        "recipients": 3,
        "sent": 3,
        "failed": 0,
        "skipped": 0,
        "dry_run": True,
    }
    logs = list(session.exec(select(SendLog)).all())
    assert len(logs) == 3
    assert all(log.status == "sent" and log.provider_id is None for log in logs)
    assert all(log.member_id is not None for log in logs)
    refreshed = session.get(Newsletter, nl.id)
    assert refreshed is not None and refreshed.status == "sent" and refreshed.sent_count == 3

    # 재호출 → 전원 스킵, 로그 증가 없음 (멱등)
    stats2 = send_newsletter(nl.id, session=session)  # pyright: ignore[reportArgumentType]
    assert stats2["skipped"] == 3 and stats2["sent"] == 0
    assert len(list(session.exec(select(SendLog)).all())) == 3


def test_send_stores_provider_id_and_replaces_unsub_url(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "test-key")
    monkeypatch.setattr(settings, "public_base_url", "https://hub.example.com")
    sent_html: list[str] = []

    def fake_send(client, *, to, subject, html, headers=None):
        sent_html.append(html)
        assert headers is not None and "List-Unsubscribe" in headers
        return f"resend-{to}"

    monkeypatch.setattr(nl_service, "send_email", fake_send)
    monkeypatch.setattr(nl_service, "SEND_INTERVAL_SECONDS", 0)
    _seed_news(session)
    _seed_members(session, 2)
    nl = build_newsletter(session, program=PROGRAM)

    stats = send_newsletter(nl.id, session=session)  # pyright: ignore[reportArgumentType]
    assert stats["sent"] == 2 and stats["dry_run"] is False
    logs = list(session.exec(select(SendLog)).all())
    assert {log.provider_id for log in logs} == {
        "resend-tester0@example.com",
        "resend-tester1@example.com",
    }
    assert all(UNSUB_PLACEHOLDER not in h for h in sent_html)
    assert any("https://hub.example.com/unsubscribe/tok-0" in h for h in sent_html)


def test_send_refuses_over_pilot_cap(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    _seed_news(session)
    _seed_members(session, PILOT_MAX_RECIPIENTS + 1)
    nl = build_newsletter(session, program=PROGRAM)
    with pytest.raises(ValueError, match="상한"):
        send_newsletter(nl.id, session=session)  # pyright: ignore[reportArgumentType]
    assert list(session.exec(select(SendLog)).all()) == []


def test_send_excludes_unsubscribed(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    _seed_news(session)
    members = _seed_members(session, 3)
    members[0].subscribed = False
    session.add(members[0])
    session.commit()
    nl = build_newsletter(session, program=PROGRAM)

    stats = send_newsletter(nl.id, session=session)  # pyright: ignore[reportArgumentType]
    assert stats["recipients"] == 2
    emails = {log.email for log in session.exec(select(SendLog)).all()}
    assert "tester0@example.com" not in emails
