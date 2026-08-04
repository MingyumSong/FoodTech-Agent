"""T-012 관리자 페이지 — 회원관리·인기분야·발송검토. 인증·필터·CRUD·집계·발송 가드 검증."""

import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog

TOKEN = "secret-token"


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _member(session: Session, name: str, email: str, *, program=None, category=None) -> Member:
    m = Member(name=name, email=email, category=category, subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    if program:
        session.add(MemberProgram(member_id=m.id, program=program))  # pyright: ignore[reportArgumentType]
        session.commit()
    return m


def _seed_diverse_news(session: Session) -> None:
    now = datetime.now(UTC)
    rows = [  # T-013: 조립 비율이 국내4:해외1이라 시드도 그에 맞춘다
        ("cell_cultured", "domestic"),
        ("plant_based", "domestic"),
        ("convenience", "domestic"),
        ("smart_manufacturing", "domestic"),
        ("food_service", "overseas"),
    ]
    for i, (cat, region) in enumerate(rows):
        session.add(
            NewsItem(
                title=f"{cat} 뉴스",
                url=f"https://news.example.com/{i}",
                summary="요약 " * 40,
                source="테스트일보",
                origin="naver" if region == "domestic" else "brave",
                region=region,
                category=cat,
                published_at=now,
                collected_at=now,
            )
        )
    session.commit()


# ------------------------------------------------------------------ 인증


def test_members_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/members").status_code == 401
    assert client.get("/admin/popular", headers=_auth("wrong")).status_code == 401


# ------------------------------------------------------------------ 탭 1: 회원 관리


def test_members_list_shows_pii_and_filters(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _member(session, "김철수", "kim@example.com", program="협의회", category="기업")
    _member(session, "이영희", "lee@example.com", program="계약학과", category="개인")

    resp = client.get("/admin/members", headers=_auth())
    assert resp.status_code == 200
    assert "김철수" in resp.text  # 관리 탭은 PII 표시 (현황판과 다름)
    assert "kim@example.com" in resp.text
    assert "협의회" in resp.text and "기업" in resp.text  # 필터 드롭다운 옵션

    # 프로그램 필터
    only = client.get("/admin/members?program=협의회", headers=_auth())
    assert "김철수" in only.text and "이영희" not in only.text
    # 이름 검색
    q = client.get("/admin/members?q=영희", headers=_auth())
    assert "이영희" in q.text and "김철수" not in q.text


def test_member_add_creates_with_program(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    resp = client.post(
        "/admin/members",
        headers=_auth(),
        data={
            "name": "박신입",
            "email": "park@example.com",
            "program": "협의회",
            "category": "기업",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    m = session.exec(select(Member).where(Member.name == "박신입")).one()
    assert m.email == "park@example.com" and m.category == "기업"
    link = session.exec(select(MemberProgram).where(MemberProgram.member_id == m.id)).one()
    assert link.program == "협의회"


def test_member_delete_detaches_tracking(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "삭제대상", "del@example.com", program="협의회")
    nl = Newsletter(subject="x", html_body="<p>x</p>", target_filter={"program": "pilot-daily"})
    session.add(nl)
    session.commit()
    session.refresh(nl)
    session.add(SendLog(newsletter_id=nl.id, member_id=m.id, email=m.email, status="sent"))  # pyright: ignore[reportArgumentType]
    session.add(
        EngagementEvent(
            member_id=m.id,
            event_type="opened",
            provider_event_id="ev-x",
            occurred_at=datetime.now(UTC),
        )
    )
    session.add(PilotMember(member_id=m.id, name=m.name))  # pyright: ignore[reportArgumentType]
    session.commit()

    resp = client.post(f"/admin/members/{m.id}/delete", headers=_auth(), follow_redirects=False)
    assert resp.status_code == 303
    assert session.get(Member, m.id) is None  # 회원 삭제됨
    # 발송 기록은 보존되되 member_id는 분리(NULL)
    log = session.exec(select(SendLog).where(SendLog.newsletter_id == nl.id)).one()
    assert log.member_id is None
    # 종속 데이터(pilot_members)는 함께 삭제
    assert session.exec(select(PilotMember).where(PilotMember.member_id == m.id)).first() is None


# ------------------------------------------------------------------ 탭 2: 인기 분야


def test_popular_aggregates_clicks_by_category(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    now = datetime.now(UTC)
    session.add(
        NewsItem(
            title="배양육",
            url="https://n/cc",
            summary="s",
            origin="naver",
            region="domestic",
            category="cell_cultured",
            collected_at=now,
        )
    )
    session.commit()
    for i in range(3):  # 같은 분야 3클릭
        session.add(
            EngagementEvent(
                event_type="clicked",
                url="https://n/cc",
                provider_event_id=f"c{i}",
                occurred_at=now,
            )
        )
    session.commit()

    resp = client.get("/admin/popular", headers=_auth())
    assert resp.status_code == 200
    assert "세포배양식품" in resp.text  # 슬러그→한글 라벨
    assert "인기 분야" in resp.text


# ------------------------------------------------------------------ 탭 4: 발송 검토


def test_review_build_then_shows_send(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")  # 게이트 전량 통과
    _seed_diverse_news(session)
    _member(session, "수신자1", "r1@example.com", program="pilot-daily")
    _member(session, "수신자2", "r2@example.com", program="pilot-daily")

    # 아직 편 없음 → 조립 버튼
    before = client.get("/admin/review", headers=_auth())
    assert "오늘 편 조립" in before.text

    built = client.post("/admin/review/build", headers=_auth(), follow_redirects=False)
    assert built.status_code == 303
    nl = session.exec(select(Newsletter)).one()
    assert (nl.target_filter or {}).get("program") == "pilot-daily"

    after = client.get("/admin/review", headers=_auth())
    assert nl.subject in after.text
    assert "지금 발송" in after.text  # 수신자 2명 → 가드 통과


def test_review_send_guards_and_dispatches(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    # 편이 없으면 400
    assert (
        client.post("/admin/review/send", headers=_auth(), follow_redirects=False).status_code
        == 400
    )

    # 편 + 수신자 준비 후 발송 수락 (send_reviewed는 스텁으로 가로채 실발송·별도 세션 방지)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _seed_diverse_news(session)
    _member(session, "수신자1", "r1@example.com", program="pilot-daily")
    client.post("/admin/review/build", headers=_auth(), follow_redirects=False)

    called: list[int] = []
    monkeypatch.setattr("app.routes.admin.send_reviewed", lambda nid: called.append(nid))
    resp = client.post("/admin/review/send", headers=_auth(), follow_redirects=False)
    assert resp.status_code == 303
    assert len(called) == 1  # 백그라운드 발송이 트리거됨
