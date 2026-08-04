"""체류 근사 — 연속 클릭 간격 (T-015).

가장 중요한 계약: **못 잰 표본이 숨지 않는다.** 편별 마지막 클릭과 상한 초과분이
각각 몇 건인지 결과에 남아야 지표를 과신하지 않는다.
"""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.newsletter import Newsletter
from app.services.dwell import (
    BOUNCE_SECONDS,
    ENGAGED_SECONDS,
    MAX_GAP_SECONDS,
    collect_dwell_stats,
    format_seconds,
)

BASE = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)


def _ids(session: Session, n_members: int = 2, n_editions: int = 2) -> tuple[list[int], list[int]]:
    """FK가 걸려 있어 실재하는 회원·뉴스레터가 있어야 이벤트를 넣을 수 있다."""
    members, editions = [], []
    for i in range(n_members):
        m = Member(name=f"독자{i}", email=f"r{i}@example.com")
        session.add(m)
        session.commit()
        session.refresh(m)
        assert m.id is not None
        members.append(m.id)
    for i in range(n_editions):
        nl = Newsletter(subject=f"푸디픽 #{i}", html_body="<p>x</p>")
        session.add(nl)
        session.commit()
        session.refresh(nl)
        assert nl.id is not None
        editions.append(nl.id)
    return members, editions


def _click(session: Session, *, member_id: int, newsletter_id: int, offset: float, tag: str):
    session.add(
        EngagementEvent(
            member_id=member_id,
            newsletter_id=newsletter_id,
            event_type="clicked",
            url=f"https://n/{tag}",
            provider_event_id=f"ev-{tag}",
            occurred_at=BASE + timedelta(seconds=offset),
        )
    )


def test_no_clicks_is_safe(session: Session):
    stats = collect_dwell_stats(session, days=30)
    assert stats["measurable"] == 0 and stats["median_seconds"] is None


def test_single_click_cannot_be_measured(session: Session):
    """클릭 1건뿐이면 잴 간격이 없다 — 못 잰 것으로 세어 드러낸다."""
    (m, _), (nl, _) = _ids(session)
    _click(session, member_id=m, newsletter_id=nl, offset=0, tag="a")
    session.commit()

    stats = collect_dwell_stats(session)
    assert stats["clicks_total"] == 1
    assert stats["measurable"] == 0
    assert stats["unmeasurable_last"] == 1


def test_gaps_are_bucketed(session: Session):
    """튕김 / 중간 / 정독으로 갈린다. 마지막 클릭은 언제나 제외."""
    (m, _), (nl, _) = _ids(session)
    for i, offset in enumerate([0, 5, 35, 300]):  # 간격 5초 · 30초 · 265초
        _click(session, member_id=m, newsletter_id=nl, offset=offset, tag=f"a{i}")
    session.commit()

    stats = collect_dwell_stats(session)
    assert stats["clicks_total"] == 4
    assert stats["measurable"] == 3  # 4건 중 마지막 1건은 못 잼
    assert stats["unmeasurable_last"] == 1
    assert stats["bounce"] == 1  # 5초
    assert stats["middle"] == 1  # 30초
    assert stats["engaged"] == 1  # 265초


def test_gap_over_cap_is_excluded_and_counted(session: Session):
    """몇 시간 뒤 다시 열어 누른 건 체류가 아니다 — 버리되 몇 건 버렸는지 남긴다."""
    (m, _), (nl, _) = _ids(session)
    _click(session, member_id=m, newsletter_id=nl, offset=0, tag="a")
    _click(session, member_id=m, newsletter_id=nl, offset=MAX_GAP_SECONDS + 1, tag="b")
    session.commit()

    stats = collect_dwell_stats(session)
    assert stats["measurable"] == 0
    assert stats["over_cap"] == 1


def test_gaps_do_not_span_editions(session: Session):
    """편이 다르면 이어 읽은 게 아니다 — 간격을 잇지 않는다."""
    (m, _), (nl1, nl2) = _ids(session)
    _click(session, member_id=m, newsletter_id=nl1, offset=0, tag="a")
    _click(session, member_id=m, newsletter_id=nl2, offset=30, tag="b")
    session.commit()

    stats = collect_dwell_stats(session)
    assert stats["measurable"] == 0
    assert stats["unmeasurable_last"] == 2  # 조합 2개, 각각 마지막 1건


def test_gaps_do_not_span_members(session: Session):
    (m1, m2), (nl, _) = _ids(session)
    _click(session, member_id=m1, newsletter_id=nl, offset=0, tag="a")
    _click(session, member_id=m2, newsletter_id=nl, offset=30, tag="b")
    session.commit()

    assert collect_dwell_stats(session)["measurable"] == 0


def test_orphan_events_are_skipped(session: Session):
    """회원·편을 못 밝힌 이벤트는 이을 수 없다(원본은 보존되지만 지표엔 안 들어감)."""
    session.add(
        EngagementEvent(
            event_type="clicked",
            url="https://n/x",
            provider_event_id="ev-orphan",
            occurred_at=BASE,
        )
    )
    session.commit()

    stats = collect_dwell_stats(session)
    assert stats["clicks_total"] == 1  # 원시 클릭 수에는 잡히고
    assert stats["unmeasurable_last"] == 0  # 조합을 못 만들어 표본엔 없다


def test_old_clicks_outside_window_are_ignored(session: Session):
    (m, _), (nl, _) = _ids(session)
    old = BASE - timedelta(days=400)
    session.add(
        EngagementEvent(
            member_id=m,
            newsletter_id=nl,
            event_type="clicked",
            provider_event_id="ev-old",
            occurred_at=old,
        )
    )
    session.commit()
    assert collect_dwell_stats(session, days=30)["clicks_total"] == 0


def test_format_seconds():
    assert format_seconds(None) == "—"
    assert format_seconds(9) == "9초"
    assert format_seconds(BOUNCE_SECONDS) == "10초"
    assert format_seconds(ENGAGED_SECONDS) == "1분 0초"
    assert format_seconds(125) == "2분 5초"
