"""뉴스레터 조립·발송 (T-008 파일럿).

설계 요점:
- 2단계 분리: build(초안 생성, 같은 날·같은 세그먼트면 기존 초안 재사용) / send(발송).
- 멱등: send 재호출 시 이미 sent인 수신자는 건너뛴다 — send_logs가 진실.
- provider_id(Resend email_id) 저장 필수 — T-003 웹훅이 member_id로 역추적하는 조인 키.
- 파일럿 가드: 수신자 100 초과 시 발송 거부 (결정 4, Resend 무료 일 100통).
- html_body에는 수신거부 URL 자리에 UNSUB_PLACEHOLDER를 저장하고 발송 시 수신자별로 치환.
"""

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.config import settings
from app.db import engine
from app.lib.email_client import send_email
from app.lib.logger import get_logger
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.send_log import SendLog
from app.services.newsletter_template import render_foodie_pick, render_text_fallback

logger = get_logger("newsletter")

PILOT_MAX_RECIPIENTS = 100  # 결정 4: 파일럿은 100명 이하 (Resend 무료 티어 일 100통)
MIN_ITEMS = 5  # 메인 2 + 에피타이저 3
UNSUB_PLACEHOLDER = "__UNSUBSCRIBE_URL__"
SEND_INTERVAL_SECONDS = 0.6  # Resend rate limit 2 req/s


def _recent_items(session: Session, days: int) -> list[NewsItem]:
    """최근 N일 뉴스 — published_at 없으면 collected_at 기준 (sim 수집분의 옛 기사 제외 효과)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    effective = func.coalesce(NewsItem.published_at, NewsItem.collected_at)
    return list(
        session.exec(select(NewsItem).where(effective >= cutoff).order_by(effective.desc())).all()
    )


def _item_dict(item: NewsItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "url": item.url,  # 원본 그대로 — 클릭 매칭(T-003) 전제, 변형 금지
        "summary": item.summary,
        "source": item.source,
        "region": item.region,
        "category": item.category,
    }


def build_newsletter(session: Session, *, program: str, days: int = 7) -> Newsletter:
    """최근 뉴스로 푸디픽 초안 생성. 같은 날 같은 세그먼트의 draft가 있으면 재사용(멱등)."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = session.exec(
        select(Newsletter)
        .where(Newsletter.status == "draft")
        .where(col(Newsletter.created_at) >= today_start)
    ).all()
    for nl in existing:
        if (nl.target_filter or {}).get("program") == program:
            return nl

    items = _recent_items(session, days)
    if len(items) < MIN_ITEMS:
        raise ValueError(f"최근 {days}일 뉴스가 {len(items)}건 — 최소 {MIN_ITEMS}건 필요")

    mains = [it for it in items if len(it.summary or "") >= 60][:2]
    main_ids = {it.id for it in mains}
    headlines = [it for it in items if it.id not in main_ids][:3]
    if len(mains) < 2 or len(headlines) < 3:
        raise ValueError("코너 구성 실패 — 요약 있는 기사 2건 + 헤드라인 3건이 필요")

    categories = {it.category for it in items}
    amuse_big = f"{len(items)}건"
    amuse_caption = f"이번 주 푸디가 새로 담은 푸드테크 뉴스 — 분야 {len(categories)}개"
    now = datetime.now(UTC)
    # 호수 = 기존 뉴스레터 수 (파일럿 첫 호 = #000, 목업 표기 규칙)
    issue_no = len(session.exec(select(Newsletter.id)).all())
    top_title = mains[0].title[:30]
    picks = len(mains) + len(headlines)

    newsletter = Newsletter(
        subject=f"푸디픽 #{issue_no} | 이번 주 푸드테크 {picks}선 — {top_title}",
        html_body=render_foodie_pick(
            issue_no=issue_no,
            issue_date=now.strftime("%Y-%m-%d"),
            amuse_big=amuse_big,
            amuse_caption=amuse_caption,
            main_items=[_item_dict(it) for it in mains],
            headline_items=[_item_dict(it) for it in headlines],
            unsubscribe_url=UNSUB_PLACEHOLDER,
        ),
        text_body=render_text_fallback(
            amuse_big=amuse_big,
            amuse_caption=amuse_caption,
            main_items=[_item_dict(it) for it in mains],
            headline_items=[_item_dict(it) for it in headlines],
        ),
        target_filter={"program": program},
        status="draft",
    )
    session.add(newsletter)
    session.commit()
    session.refresh(newsletter)
    logger.info(f"newsletter draft built: id={newsletter.id} items={len(items)}")
    return newsletter


def _recipients(session: Session, program: str) -> list[Member]:
    """세그먼트 수신자 — subscribed + 이메일 보유, 이메일 기준 중복 제거."""
    rows = session.exec(
        select(Member)
        .join(MemberProgram, col(MemberProgram.member_id) == col(Member.id))
        .where(MemberProgram.program == program)
        .where(Member.subscribed == True)  # noqa: E712
        .where(col(Member.email).is_not(None))
        .where(Member.email != "")
        .order_by(col(Member.id))
    ).all()
    seen: set[str] = set()
    unique: list[Member] = []
    for m in rows:
        key = (m.email or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(m)
    return unique


def send_newsletter(
    newsletter_id: int,
    session: Session | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """뉴스레터 발송 — 멱등(이미 sent인 수신자 스킵), 100명 가드, provider_id 저장."""
    if session is None:
        with Session(engine) as own:
            return send_newsletter(newsletter_id, session=own, client=client)
    if client is None:
        with httpx.Client() as own_client:
            return send_newsletter(newsletter_id, session=session, client=own_client)

    newsletter = session.get(Newsletter, newsletter_id)
    if newsletter is None:
        raise ValueError(f"newsletter {newsletter_id} 없음")
    program = (newsletter.target_filter or {}).get("program")
    if not program:
        raise ValueError("target_filter.program 없음 — 세그먼트 없는 발송 금지")

    recipients = _recipients(session, program)
    if len(recipients) > PILOT_MAX_RECIPIENTS:
        raise ValueError(
            f"수신자 {len(recipients)}명 > 파일럿 상한 {PILOT_MAX_RECIPIENTS} — 발송 거부 (결정 4)"
        )

    # 멱등 키: 이 뉴스레터의 기존 send_logs (이메일 기준)
    logs = {
        log.email: log
        for log in session.exec(select(SendLog).where(SendLog.newsletter_id == newsletter_id)).all()
    }

    newsletter.status = "sending"
    newsletter.total_recipients = len(recipients)
    session.add(newsletter)
    session.commit()

    dry_run = not settings.resend_api_key
    sent = failed = skipped = 0
    for member in recipients:
        email = (member.email or "").strip()
        log = logs.get(email)
        if log is not None and log.status == "sent":
            skipped += 1
            continue
        if log is None:
            log = SendLog(newsletter_id=newsletter_id, member_id=member.id, email=email)

        if not member.unsubscribe_token:
            member.unsubscribe_token = secrets.token_urlsafe(16)
            session.add(member)
        unsub_url = f"{settings.public_base_url}/unsubscribe/{member.unsubscribe_token}"

        try:
            provider_id = send_email(
                client,
                to=email,
                subject=newsletter.subject,
                html=newsletter.html_body.replace(UNSUB_PLACEHOLDER, unsub_url),
                headers={
                    "List-Unsubscribe": f"<{unsub_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",  # RFC 8058
                },
            )
            log.status = "sent"
            log.provider_id = provider_id  # DRY RUN이면 None (Postgres unique는 NULL 중복 허용)
            sent += 1
        except Exception as exc:  # 수신자 단위 격리 — 한 명 실패가 전체를 막지 않는다
            log.status = "failed"
            log.error = f"{type(exc).__name__}: {exc}"[:500]
            failed += 1
            logger.warning(f"send failed (member_id={member.id}): {type(exc).__name__}")
        session.add(log)
        session.commit()  # 통 단위 커밋 — 중단돼도 보낸 기록은 남는다
        if not dry_run:
            time.sleep(SEND_INTERVAL_SECONDS)

    newsletter.status = "sent"
    newsletter.sent_at = datetime.now(UTC)
    newsletter.sent_count = sum(
        1
        for r in session.exec(select(SendLog).where(SendLog.newsletter_id == newsletter_id)).all()
        if r.status == "sent"
    )
    newsletter.failed_count = failed
    session.add(newsletter)
    session.commit()

    stats = {
        "newsletter_id": newsletter_id,
        "recipients": len(recipients),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "dry_run": dry_run,
    }
    logger.info(f"newsletter send done: {stats}")
    return stats
