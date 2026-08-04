"""T-017 Activity Score — 점수 공식·등급 컷·DB 산출 검증.

실데이터에서 관찰된 함정을 그대로 케이스로 만든다:
같은 편 재열람 22회, open 0인데 클릭 5회, 발송 1건뿐인 회원, 발송 직후(<10초) 열람.
"""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog
from app.services.activity_score import (
    ACTIVE_CUT,
    BOT_OPEN_SECONDS,
    HALF_LIFE_DAYS,
    WARM_CUT,
    WINDOW_DAYS,
    Delivery,
    percentile_ranks,
    score_deliveries,
    score_members,
)
from app.services.pilot_daily import PILOT_PROGRAM, refresh_pilot_stats

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def _d(days_ago: float, **kw) -> Delivery:
    return Delivery(sent_at=NOW - timedelta(days=days_ago), **kw)


# ------------------------------------------------------------ 공식 (AC1~5)


def test_no_engagement_scores_zero_but_stays_dormant_not_unknown():
    """발송은 받았는데 아무 반응이 없으면 0점 dormant — 판단 근거가 없는 unknown과 구분된다."""
    result = score_deliveries([_d(i) for i in range(9)], now=NOW)
    assert result.score == 0.0
    assert result.tier == "dormant"
    assert result.window_sends == 9
    assert result.engaged_sends == 0


def test_click_outweighs_open_and_reaction_outweighs_click():
    """결정 5의 순서: 열람 < 클릭 < (전달 대신) 원클릭 반응."""
    days = list(range(9))
    opened = score_deliveries([_d(i, opened=True) for i in days], now=NOW)
    clicked = score_deliveries([_d(i, clicked_urls={"u"}) for i in days], now=NOW)
    reacted = score_deliveries([_d(i, reacted=True) for i in days], now=NOW)
    assert opened.score < clicked.score < reacted.score


def test_click_depth_raises_score_but_is_capped():
    """같은 편에서 여러 기사를 누르면 더 높지만, 무한정 오르지는 않는다."""
    one = score_deliveries([_d(1, clicked_urls={"a"})], now=NOW)
    three = score_deliveries([_d(1, clicked_urls={"a", "b", "c"})], now=NOW)
    many = score_deliveries([_d(1, clicked_urls={f"u{i}" for i in range(20)})], now=NOW)
    assert one.score < three.score < many.score
    # 깊이 상한(+2) 때문에 URL 5개와 20개는 같은 값
    five = score_deliveries([_d(1, clicked_urls={f"u{i}" for i in range(5)})], now=NOW)
    assert five.score == many.score


def test_click_without_open_still_scores():
    """실데이터: open 0인데 클릭 5회인 회원(이미지 차단). 열람 없이도 클릭은 온전히 센다."""
    result = score_deliveries(
        [_d(i, opened=False, clicked_urls={f"u{i}"}) for i in range(4)], now=NOW
    )
    assert result.score > 0
    assert result.clicked_sends == 4


def test_single_send_is_shrunk_below_25():
    """AC4: 발송 1건뿐인 회원은 만점을 받아도 25점을 넘지 못한다 (축소).

    실데이터의 6051번 — 1건 발송에 URL 9개 클릭. 축소가 없으면 90점으로 1위가 된다.
    """
    result = score_deliveries(
        [_d(0, opened=True, reacted=True, clicked_urls={f"u{i}" for i in range(9)})], now=NOW
    )
    assert result.score <= 25.0
    assert result.tier == "warm"  # active는 아니다 — 표본이 부족하므로 단정하지 않는다


def test_recent_engagement_beats_old_engagement():
    """AC5: 같은 반응량이면 최근에 낸 쪽이 높다 (반감기 감쇠)."""
    recent = score_deliveries([_d(1, clicked_urls={"u"}) for _ in range(3)], now=NOW)
    old = score_deliveries(
        [_d(HALF_LIFE_DAYS * 2 + 1, clicked_urls={"u"}) for _ in range(3)], now=NOW
    )
    assert recent.score > old.score


def test_deliveries_outside_window_are_ignored():
    """창(120일) 밖 발송은 분모에서도 빠진다 — 오래된 무반응이 영원히 점수를 눌러앉히지 않는다."""
    result = score_deliveries(
        [_d(WINDOW_DAYS + 10) for _ in range(50)] + [_d(1, clicked_urls={"u"})], now=NOW
    )
    assert result.window_sends == 1


# ------------------------------------------------------------ 등급 (AC6)


def test_tier_cuts_are_absolute():
    active = score_deliveries([_d(i, clicked_urls={"a", "b", "c"}) for i in range(12)], now=NOW)
    assert active.score >= ACTIVE_CUT and active.tier == "active"
    warm = score_deliveries([_d(i, opened=True) for i in range(12)], now=NOW)
    assert WARM_CUT <= warm.score < ACTIVE_CUT and warm.tier == "warm"


def test_never_sent_is_unknown_not_dormant():
    """AC6: 안 보내놓고 비활동으로 낙인찍지 않는다."""
    assert score_deliveries([], now=NOW).tier == "unknown"


def test_unsubscribed_is_its_own_tier():
    result = score_deliveries([_d(1, clicked_urls={"u"})], now=NOW, subscribed=False)
    assert result.tier == "unsubscribed"


def test_percentile_ranks_are_relative_positions():
    ranks = percentile_ranks({1: 50.0, 2: 10.0, 3: 30.0})
    assert ranks[1] > ranks[3] > ranks[2]
    assert all(0 <= v <= 100 for v in ranks.values())
    assert percentile_ranks({}) == {}


# ------------------------------------------------------------ DB 경로 (AC3/7)


def _member(session: Session, name: str, *, subscribed: bool = True) -> Member:
    m = Member(name=name, email=f"{name}@example.com", subscribed=subscribed)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def _newsletter(session: Session, subject: str) -> Newsletter:
    nl = Newsletter(subject=subject, html_body="<p>x</p>", status="sent")
    session.add(nl)
    session.commit()
    session.refresh(nl)
    return nl


def _sent(session: Session, member: Member, nl: Newsletter, when: datetime) -> SendLog:
    log = SendLog(
        newsletter_id=nl.id or 0,
        member_id=member.id,
        email=member.email or "",
        status="sent",
        created_at=when,
    )
    session.add(log)
    session.commit()
    return log


def _event(
    session: Session,
    member: Member,
    nl: Newsletter,
    event_type: str,
    when: datetime,
    url: str | None = None,
) -> None:
    session.add(
        EngagementEvent(
            member_id=member.id,
            newsletter_id=nl.id,
            event_type=event_type,
            url=url,
            provider_event_id=f"{member.id}:{nl.id}:{event_type}:{when.isoformat()}:{url}",
            occurred_at=when,
        )
    )
    session.commit()


def test_bot_open_within_10s_is_ignored_but_click_is_not(session: Session):
    """AC3: 발송 후 10초 이내 열람은 스캐너로 보고 버린다. 같은 구간의 클릭은 정상 반영."""
    sent_at = NOW - timedelta(days=1)
    bot = _member(session, "bot-open")
    human = _member(session, "fast-click")
    nl = _newsletter(session, "테스트 편")
    _sent(session, bot, nl, sent_at)
    _sent(session, human, nl, sent_at)
    _event(session, bot, nl, "opened", sent_at + timedelta(seconds=BOT_OPEN_SECONDS - 5))
    _event(session, human, nl, "clicked", sent_at + timedelta(seconds=5), url="https://a/1")

    scores = score_members(session, [bot.id or 0, human.id or 0], now=NOW)
    assert scores[bot.id or 0].score == 0.0  # 봇 열람은 없던 일
    assert scores[human.id or 0].score > 0.0


def test_reopening_the_same_issue_does_not_raise_score(session: Session):
    """AC2: 실데이터의 raw open 22회 회원. 같은 편 재열람은 점수를 1회분으로 수렴시킨다."""
    sent_at = NOW - timedelta(days=1)
    once = _member(session, "opened-once")
    many = _member(session, "opened-22-times")
    nl = _newsletter(session, "재열람 편")
    _sent(session, once, nl, sent_at)
    _sent(session, many, nl, sent_at)
    _event(session, once, nl, "opened", sent_at + timedelta(minutes=10))
    for i in range(22):
        _event(session, many, nl, "opened", sent_at + timedelta(minutes=10 + i))

    scores = score_members(session, [once.id or 0, many.id or 0], now=NOW)
    assert scores[many.id or 0].score == scores[once.id or 0].score > 0
    assert scores[many.id or 0].engaged_sends == 1


def test_score_members_covers_members_without_any_send(session: Session):
    lonely = _member(session, "no-send")
    scores = score_members(session, [lonely.id or 0], now=NOW)
    assert scores[lonely.id or 0].tier == "unknown"


def test_refresh_pilot_stats_writes_score_and_is_idempotent(session: Session):
    """AC7: 롤업이 점수·등급·갱신시각을 채우고, 두 번 돌려도 점수가 같다."""
    m = _member(session, "pilot-one")
    session.add(MemberProgram(member_id=m.id or 0, program=PILOT_PROGRAM))
    session.commit()
    nl = _newsletter(session, "파일럿 편")
    sent_at = datetime.now(UTC) - timedelta(days=1)
    _sent(session, m, nl, sent_at)
    _event(session, m, nl, "clicked", sent_at + timedelta(minutes=5), url="https://a/1")

    refresh_pilot_stats(session)
    pm = session.exec(select(PilotMember).where(PilotMember.member_id == m.id)).one()
    first_score, first_tier = pm.activity_score, pm.activity_tier
    assert first_score > 0
    assert first_tier in {"active", "warm", "dormant"}
    assert pm.score_updated_at is not None

    refresh_pilot_stats(session)
    session.refresh(pm)
    assert (pm.activity_score, pm.activity_tier) == (first_score, first_tier)
