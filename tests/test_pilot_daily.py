"""T-011 파일럿 매일발송 — 분야 다양성·일별 회전·통계 롤업 검증."""

from datetime import UTC, datetime, timedelta

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
    pilot_send_status,
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


def test_mains_are_chosen_by_depth_not_list_order():
    """메인 자리는 '국내 목록의 앞 두 개'가 아니라 **심도 있는 기사**가 차지한다 (T-024).

    이걸 안 하면 실제로 벌어진 일: #018 메인 1번이 `[경제인칼럼] 동네상권 위기의 외식업`이었고
    `top_title = mains[0]`이라 메일 제목까지 그 칼럼이었다.
    """
    pool = _diverse_pool()
    # 국내 목록의 뒤쪽 두 건에만 심도를 준다 — 순서만 따르면 절대 메인에 못 오는 자리다.
    deep = {DOM[2], DOM[3]}
    pool = [{**it, "depth": 5 if it["category"] in deep else 2} for it in pool]

    picks = select_picks(pool, day_index=0)
    mains = picks[:3]
    assert {p["category"] for p in mains if p["region"] == "domestic"} == deep


def test_picks_unchanged_when_gate_gave_no_depth():
    """심도 판정이 없으면 예전 순서 그대로 — 게이트가 죽어도 편성이 흔들리면 안 된다."""
    pool = _diverse_pool()
    assert select_picks(pool, day_index=0) == select_picks([{**it} for it in pool], day_index=0)
    plain = select_picks(pool, day_index=3)
    lighted = select_picks([{**it, "depth": 2} for it in pool], day_index=3)
    assert [p["category"] for p in plain] == [p["category"] for p in lighted]


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

    # 실린 기사 URL을 남긴다 — 다음 편이 같은 기사를 피하는 근거 (T-024)
    urls = (nl1.target_filter or {}).get("item_urls") or []
    assert len(urls) == 5 and all(u.startswith("https://") for u in urls)


def test_next_edition_skips_articles_already_sent(session: Session, monkeypatch):
    """같은 기사가 이틀 연속 나가지 않는다 (T-024).

    심도 우선 정렬을 넣으면서 '분야별 최신 1건'이 만들던 자연스러운 교체가 깨졌다 —
    심도 높은 기사가 7일 창 내내 자기 분야 맨 앞을 지킨다.
    """
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _seed_diverse_news(session)

    first = build_pilot_daily(session)
    used = set((first.target_filter or {}).get("item_urls") or [])

    # 어제 편으로 만들어 오늘 편이 새로 조립되게 한다
    first.created_at = datetime.now(UTC) - timedelta(days=1)
    session.add(first)
    session.commit()

    # 대체 기사를 **더 오래된 것으로** 넣는다. 이래야 배제가 진짜 일하는지 드러난다 —
    # 새 기사가 더 최신이면 '분야별 최신 1건' 규칙만으로도 교체돼서 테스트가 헛돈다.
    # 제목은 원본과도, **서로와도** 겹치면 안 된다 — 겹치면 T-009 중복 병합이 먼저 삼켜서
    # 배제 로직에 도달하지 못한다. 이 테스트가 그 함정에 두 번 빠졌다:
    # 처음엔 원본과 비슷해서, 다음엔 예비끼리 공통 어절("전혀다른회사 신규발표")이 있어서.
    spare_titles = "가나다 라마바 사아자 차카타 파하거 너더러 머버서 어저처".split()
    older = datetime.now(UTC) - timedelta(hours=6)
    for i, cat in enumerate(DOM + OV):
        session.add(
            NewsItem(
                title=spare_titles[i],
                url=f"https://news.example.com/spare/{cat}/{i}",
                summary="요약 " * 40,
                source="테스트일보",
                origin="naver" if cat in DOM else "brave",
                region="domestic" if cat in DOM else "overseas",
                category=cat,
                published_at=older,
                collected_at=older,
            )
        )
    session.commit()

    second = build_pilot_daily(session)
    assert second.id != first.id
    again = set((second.target_filter or {}).get("item_urls") or [])
    assert not (again & used), "어제 실린 기사가 오늘 또 실렸다"


def test_thin_pool_keeps_sending_rather_than_starving(session: Session, monkeypatch):
    """배제하면 꼭지를 못 채우는 날엔 배제를 포기한다 — 발송 자체가 없어지는 게 더 나쁘다."""
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _seed_diverse_news(session)  # 딱 8건 — 5꼭지 쓰고 나면 남는 게 없다

    first = build_pilot_daily(session)
    first.created_at = datetime.now(UTC) - timedelta(days=1)
    session.add(first)
    session.commit()

    second = build_pilot_daily(session)  # 예외 없이 조립돼야 한다
    assert second.id != first.id
    used = set((first.target_filter or {}).get("item_urls") or [])
    again = set((second.target_filter or {}).get("item_urls") or [])
    assert len(again) == 5
    assert again & used, "대체할 기사가 없으면 기존 기사를 다시 써서라도 발송한다"


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


def test_send_status_reports_no_edition_when_nothing_built(session: Session):
    """오늘 편이 없으면 실패로 답한다 — 크론이 이걸 보고 빨간불을 켠다 (T-028)."""
    assert pilot_send_status(session) == {"ok": False, "reason": "no_edition_today", "sent": 0}


def test_send_status_distinguishes_built_from_sent(session: Session, monkeypatch):
    """**조립만 된 편은 성공이 아니다.**

    조용한 실패의 정확한 모양이 이것이다 — 트리거는 202로 수락되고 편은 만들어졌는데
    발송에서 터진다. 상태가 sent이고 실제로 나간 통수가 있어야 ok다.
    """
    monkeypatch.setattr(settings, "openrouter_api_key", "")  # 게이트 전량 통과
    _seed_diverse_news(session)
    nl = build_pilot_daily(session)
    assert nl.id is not None  # commit·refresh 후라 항상 존재

    built = pilot_send_status(session)
    assert built["ok"] is False and built["newsletter_id"] == nl.id

    session.add(SendLog(newsletter_id=nl.id, member_id=None, email="a@b.c", status="sent"))
    nl.status = "sent"
    session.add(nl)
    session.commit()

    assert pilot_send_status(session)["ok"] is True
    assert pilot_send_status(session)["sent"] == 1


def test_send_status_ignores_failed_logs(session: Session, monkeypatch):
    """실패한 발송만 있으면 ok가 아니다 — 통수 0인 '발송 완료'는 발송이 아니다."""
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _seed_diverse_news(session)
    nl = build_pilot_daily(session)
    assert nl.id is not None
    nl.status = "sent"
    session.add(nl)
    session.add(
        SendLog(newsletter_id=nl.id, member_id=None, email="a@b.c", status="failed", error="boom")
    )
    session.commit()

    status = pilot_send_status(session)
    assert status["ok"] is False and status["sent"] == 0
