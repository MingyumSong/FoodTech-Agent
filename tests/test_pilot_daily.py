"""T-011 파일럿 매일발송 — 분야 다양성·일별 회전·통계 롤업 검증."""

from datetime import UTC, datetime

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog
from app.services.pilot_daily import (
    PILOT_PROGRAM,
    ROTATION_CATEGORIES,
    build_pilot_daily,
    refresh_pilot_stats,
    select_picks,
)

DOM = ROTATION_CATEGORIES[:5]  # 국내에 쓸 분야 5종
OV = ROTATION_CATEGORIES[5:8]  # 해외에 쓸 분야 3종


def _item(cat: str, region: str, i: int) -> dict:
    return {
        "title": f"{cat} 뉴스 {i}",
        "url": f"https://news.example.com/{region}/{cat}/{i}",
        "summary": "요약 " * 40,  # 충분히 긺
        "source": "테스트일보",
        "region": region,
        "category": cat,
    }


def _diverse_pool() -> list[dict]:
    dom = [_item(c, "domestic", i) for i, c in enumerate(DOM)]
    ov = [_item(c, "overseas", i) for i, c in enumerate(OV)]
    return dom + ov


# ------------------------------------------------------------ select_picks (AC2/3)


def test_select_picks_ratio_and_diversity():
    """국내4:해외1 비율 + 한 편 안에서 분야가 겹치지 않는다 (T-013: '국내 위주로' 피드백)."""
    picks = select_picks(_diverse_pool(), day_index=0)
    assert len(picks) == 5
    assert sum(p["region"] == "domestic" for p in picks) == 4
    assert sum(p["region"] == "overseas" for p in picks) == 1
    cats = [p["category"] for p in picks]
    assert len(set(cats)) == 5  # 5꼭지 전부 다른 분야


def test_select_picks_orders_mains_then_headlines():
    """반환 순서 = 메인 국내2 + 메인 해외1 + 에피타이저 국내2.

    build_pilot_daily가 이 순서를 그대로 잘라 코너에 넣으므로 순서가 계약이다.
    """
    picks = select_picks(_diverse_pool(), day_index=0)
    assert [p["region"] for p in picks] == [
        "domestic",
        "domestic",
        "overseas",
        "domestic",
        "domestic",
    ]


def test_select_picks_rotates_across_days():
    """연속한 날이면 선정 분야 집합이 달라진다 (콜드스타트 다양성)."""
    pool = _diverse_pool()
    day0 = {p["category"] for p in select_picks(pool, day_index=10)}
    day1 = {p["category"] for p in select_picks(pool, day_index=11)}
    assert day0 != day1


def test_select_picks_raises_when_thin():
    """게이트 통과분이 얇으면(비율 못 채우면) 발송을 막는다."""
    thin = [_item(DOM[0], "domestic", 0), _item(OV[0], "overseas", 0)]
    with pytest.raises(ValueError, match="꼭지 부족"):
        select_picks(thin, day_index=0)


# ------------------------------------------------------------ build_pilot_daily (AC2, 멱등)


def _seed_diverse_news(session: Session) -> None:
    now = datetime.now(UTC)
    for it in _diverse_pool():
        session.add(
            NewsItem(
                title=it["title"],
                url=it["url"],
                summary=it["summary"],
                source=it["source"],
                origin="naver" if it["region"] == "domestic" else "brave",
                region=it["region"],
                category=it["category"],
                published_at=now,
                collected_at=now,
            )
        )
    session.commit()


def test_build_pilot_daily_reuses_same_day_edition(session: Session, monkeypatch):
    """같은 날 재호출은 새 편을 만들지 않고 재사용한다(멱등). 배너·수신거부 자리 포함."""
    monkeypatch.setattr(settings, "openrouter_api_key", "")  # 게이트 전량 통과
    _seed_diverse_news(session)

    nl1 = build_pilot_daily(session)
    assert (nl1.target_filter or {}).get("program") == PILOT_PROGRAM
    assert "🧪 시범 운영 중" in nl1.html_body  # 파일럿 배너
    assert "__UNSUBSCRIBE_URL__" in nl1.html_body  # 수신자별 치환 자리

    nl2 = build_pilot_daily(session)
    assert nl2.id == nl1.id  # 재사용
    assert len(session.exec(select(Newsletter.id)).all()) == 1


# ------------------------------------------------------------ refresh_pilot_stats (AC5)


def test_refresh_pilot_stats_rolls_up_and_is_idempotent(session: Session):
    """send_logs·engagement_events를 pilot_members로 멱등 롤업(분야별 클릭 포함)."""
    # 뉴스(클릭 URL→분야 매칭용)
    now = datetime.now(UTC)
    a = NewsItem(
        title="A",
        url="https://n/a",
        summary="s",
        origin="naver",
        region="domestic",
        category="cell_cultured",
        collected_at=now,
    )
    b = NewsItem(
        title="B",
        url="https://n/b",
        summary="s",
        origin="naver",
        region="domestic",
        category="plant_based",
        collected_at=now,
    )
    session.add(a)
    session.add(b)
    nl = Newsletter(subject="x", html_body="<p>x</p>", target_filter={"program": PILOT_PROGRAM})
    session.add(nl)
    session.commit()
    session.refresh(nl)

    # 회원 2명 — pilot-daily 프로그램 링크
    m0 = Member(name="김철수", email="a@example.com")
    m1 = Member(name="이영희", email="b@example.com")
    for m in (m0, m1):
        session.add(m)
        session.commit()
        session.refresh(m)
        session.add(MemberProgram(member_id=m.id, program=PILOT_PROGRAM))  # pyright: ignore[reportArgumentType]
    session.commit()

    # m0: 발송 2 + 열람 1 + 클릭 2(분야 각 1)  / m1: 발송 1, 추적 0
    for _ in range(2):
        session.add(
            SendLog(newsletter_id=nl.id, member_id=m0.id, email=m0.email, status="sent")  # pyright: ignore[reportArgumentType]
        )
    session.add(
        SendLog(newsletter_id=nl.id, member_id=m1.id, email=m1.email, status="sent")  # pyright: ignore[reportArgumentType]
    )
    session.add(
        EngagementEvent(
            member_id=m0.id, event_type="opened", provider_event_id="ev-open-0", occurred_at=now
        )
    )
    session.add(
        EngagementEvent(
            member_id=m0.id,
            event_type="clicked",
            url="https://n/a",
            provider_event_id="ev-c-a",
            occurred_at=now,
        )
    )
    session.add(
        EngagementEvent(
            member_id=m0.id,
            event_type="clicked",
            url="https://n/b",
            provider_event_id="ev-c-b",
            occurred_at=now,
        )
    )
    session.commit()

    stats = refresh_pilot_stats(session)
    assert stats == {"members": 2, "created": 2, "updated": 0}

    pm0 = session.exec(select(PilotMember).where(PilotMember.member_id == m0.id)).one()
    assert (pm0.emails_sent, pm0.emails_opened, pm0.links_clicked) == (2, 1, 2)
    assert pm0.category_clicks == {"cell_cultured": 1, "plant_based": 1}
    assert pm0.last_clicked_at is not None

    pm1 = session.exec(select(PilotMember).where(PilotMember.member_id == m1.id)).one()
    assert (pm1.emails_sent, pm1.emails_opened, pm1.links_clicked) == (1, 0, 0)

    # 재호출: 새 행을 만들지 않고 갱신만 (멱등)
    again = refresh_pilot_stats(session)
    assert again == {"members": 2, "created": 0, "updated": 2}
    assert len(session.exec(select(PilotMember.id)).all()) == 2
