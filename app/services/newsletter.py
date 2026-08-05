"""뉴스레터 조립·발송 (T-008 파일럿).

설계 요점:
- 2단계 분리: build(초안 생성, 같은 날·같은 세그먼트면 기존 초안 재사용) / send(발송).
- 멱등: send 재호출 시 이미 sent인 수신자는 건너뛴다 — send_logs가 진실.
- provider_id(Resend email_id) 저장 필수 — T-003 웹훅이 member_id로 역추적하는 조인 키.
- 파일럿 가드: 수신자 100 초과 시 발송 거부 (결정 4, Resend 무료 일 100통).
- html_body에는 수신거부 URL·반응 링크 자리에 플레이스홀더를 저장하고 발송 시 수신자별로 치환
  (UNSUB_PLACEHOLDER, REACTION_BASE_PLACEHOLDER).
- **대상은 조립 시점에 확정한다**(T-023). 등급(tiers)을 주면 `target_filter.member_ids`로 얼려
  저장하고 발송은 그 목록으로 좁히기만 한다 — 발송이 send_logs에 무반응 1건을 더해 점수를
  낮추므로, 발송 시점에 등급을 계산하면 재시도에서 대상이 사라진다.
  단 수신거부는 얼리지 않고 발송 시점 목록과 교집합을 취한다.
"""

import secrets
import time
from collections.abc import Sequence
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
from app.services.activity_score import score_members
from app.services.curation import curate_articles
from app.services.newsletter_template import (
    REACTION_BASE_PLACEHOLDER,
    render_foodie_pick,
    render_text_fallback,
)

logger = get_logger("newsletter")

PILOT_MAX_RECIPIENTS = 100  # 결정 4: 파일럿은 100명 이하 (Resend 무료 티어 일 100통)
MIN_ITEMS = 5  # 에피타이저 2 + 메인 3 (T-013에서 뒤집힘 — 이전은 에피 3 + 메인 2)
N_MAINS = 3
N_HEADLINES = 2
UNSUB_PLACEHOLDER = "__UNSUBSCRIBE_URL__"
SEND_INTERVAL_SECONDS = 0.6  # Resend rate limit 2 req/s


def icon_url() -> str:
    """이메일 헤더 아이콘의 절대 URL — 메일 클라이언트는 상대 경로를 못 푼다."""
    return f"{settings.public_base_url}/static/foodie-icon.png"


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


def build_newsletter(
    session: Session, *, program: str, days: int = 7, tiers: Sequence[str] | None = None
) -> Newsletter:
    """최근 뉴스로 푸디픽 초안 생성. 같은 날 같은 세그먼트의 draft가 있으면 재사용(멱등).

    `tiers`를 주면 발송 대상을 Activity Score 등급으로 좁힌다(T-023) — 발송 시점에 적용되도록
    `target_filter`에 저장만 하고, 조립 내용은 바뀌지 않는다.
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = session.exec(
        select(Newsletter)
        .where(Newsletter.status == "draft")
        .where(col(Newsletter.created_at) >= today_start)
    ).all()
    wanted_tiers = sorted(tiers) if tiers else None
    for nl in existing:
        tf = nl.target_filter or {}
        # 대상 등급이 다르면 다른 초안이다 — 재사용하면 의도한 대상 대신 옛 대상에게 나간다.
        if tf.get("program") == program and (tf.get("tiers") or None) == wanted_tiers:
            return nl

    items = _recent_items(session, days)
    # 묶음기사 제외 + 같은 사건 중복 병합 (T-009). 이 경로엔 뉴스가치 판단이 전혀 없어서
    # 정리 없이는 5칸 중 두 칸이 같은 뉴스가 될 수 있다.
    before = len(items)
    items = curate_articles(items)
    if len(items) < before:
        logger.info(
            f"newsletter curate: {before} → {len(items)} (묶음·중복 {before - len(items)}건 제외)"
        )
    if len(items) < MIN_ITEMS:
        raise ValueError(f"최근 {days}일 뉴스가 {len(items)}건 — 최소 {MIN_ITEMS}건 필요")

    mains = [it for it in items if len(it.summary or "") >= 60][:N_MAINS]
    main_ids = {it.id for it in mains}
    headlines = [it for it in items if it.id not in main_ids][:N_HEADLINES]
    if len(mains) < N_MAINS or len(headlines) < N_HEADLINES:
        raise ValueError(
            f"코너 구성 실패 — 요약 있는 기사 {N_MAINS}건 + 헤드라인 {N_HEADLINES}건이 필요"
        )

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
            main_items=[_item_dict(it) for it in mains],
            headline_items=[_item_dict(it) for it in headlines],
            unsubscribe_url=UNSUB_PLACEHOLDER,
            icon_url=icon_url(),
        ),
        text_body=render_text_fallback(
            main_items=[_item_dict(it) for it in mains],
            headline_items=[_item_dict(it) for it in headlines],
        ),
        target_filter=_target_filter(session, program, wanted_tiers),
        status="draft",
    )
    session.add(newsletter)
    session.commit()
    session.refresh(newsletter)
    logger.info(f"newsletter draft built: id={newsletter.id} items={len(items)}")
    return newsletter


def _recipients(
    session: Session, program: str, *, tiers: Sequence[str] | None = None
) -> list[Member]:
    """세그먼트 수신자 — subscribed + 이메일 보유, 이메일 기준 중복 제거.

    `tiers`를 주면 Activity Score 등급이 그 안에 드는 회원만 남긴다 (T-023).
    **없으면 기존 동작 그대로** — 등급 계산도 하지 않는다.
    등급은 목록을 좁히기만 하므로 100명 가드·멱등에는 영향이 없다.
    """
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

    if not tiers:
        return unique
    wanted = set(tiers)
    ids = [m.id for m in unique if m.id is not None]
    scores = score_members(session, ids)  # 배치 — 회원이 늘어도 왕복은 그대로
    picked = [m for m in unique if m.id is not None and (scores[m.id].tier in wanted)]
    logger.info(f"tier filter: {len(unique)} → {len(picked)} (tiers={sorted(wanted)})")
    return picked


def _target_filter(session: Session, program: str, tiers: list[str] | None) -> dict[str, Any]:
    """이 편의 발송 대상을 **조립 시점에 확정**해 저장한다 (T-023).

    등급을 발송 시점에 계산하면 안 된다 — 발송 자체가 `send_logs`에 무반응 1건을 더해
    점수를 떨어뜨리기 때문에, 재시도할 때 등급이 바뀌어 **받아야 할 사람이 빠진다**
    (실측: 재발송에서 대상 1명 → 0명). 대상은 한 번 정하고 얼려둔다.

    수신거부는 얼리지 않는다 — 발송 시점에 다시 확인해 조립 후 해지한 사람을 뺀다.
    """
    if not tiers:
        return {"program": program}
    picked = _recipients(session, program, tiers=tiers)
    return {
        "program": program,
        "tiers": tiers,
        "member_ids": sorted(m.id for m in picked if m.id is not None),
    }


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
    target = newsletter.target_filter or {}
    program = target.get("program")
    if not program:
        raise ValueError("target_filter.program 없음 — 세그먼트 없는 발송 금지")

    # 대상은 조립 때 확정된다(T-023). 여기선 그 목록으로 좁히기만 한다 —
    # 등급을 지금 다시 계산하면 이 발송 자체가 점수를 바꿔 재시도에서 대상이 흔들린다.
    recipients = _recipients(session, program)
    frozen = target.get("member_ids")
    if frozen is not None:
        keep = set(frozen)
        # 조립 후 수신거부한 사람은 _recipients가 이미 뺐다 — 교집합이라 되살아나지 않는다.
        recipients = [m for m in recipients if m.id in keep]
        logger.info(f"frozen target: {len(keep)}명 중 발송 가능 {len(recipients)}명")
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
        # 반응 링크도 수신자별로 확정한다 — 토큰은 수신거부와 같은 것을 쓴다(T-013 라우트 주석 참고)
        reaction_base = (
            f"{settings.public_base_url}/reactions/{member.unsubscribe_token}/{newsletter_id}"
        )
        html = newsletter.html_body.replace(UNSUB_PLACEHOLDER, unsub_url).replace(
            REACTION_BASE_PLACEHOLDER, reaction_base
        )

        try:
            provider_id = send_email(
                client,
                to=email,
                subject=newsletter.subject,
                html=html,
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
