"""T-012 관리자 페이지 — 회원관리·인기분야·발송검토. 인증·필터·CRUD·집계·발송 가드 검증."""

import base64
from datetime import UTC, datetime, timedelta

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
from app.services.admin_pages import _tier_chip

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


def test_admin_can_restore_unsubscribed_member(client: TestClient, session: Session, monkeypatch):
    """수신거부한 회원을 되살리는 유일한 경로 (T-025).

    이게 없어서 "다시 받고 싶으면 연락주세요"라는 안내가 빈말이었다 —
    연락을 받아도 직원이 DB를 직접 쓰는 것 말고 방법이 없었다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "돌아온회원", "back@example.com")
    m.subscribed = False
    session.add(m)
    session.commit()
    before = m.updated_at

    resp = client.post(
        f"/admin/members/{m.id}/subscribed",
        data={"subscribed": "1"},
        headers=_auth(),
        follow_redirects=False,
    )
    assert resp.status_code == 303
    session.refresh(m)
    assert m.subscribed is True
    assert m.updated_at > before  # 언제 되살렸는지도 남는다


def test_admin_subscription_toggle_is_idempotent(client: TestClient, session: Session, monkeypatch):
    """같은 값으로 다시 눌러도 updated_at을 흔들지 않는다 — 이탈 시점 기록이 지워지면 안 된다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "구독중", "keep@example.com")
    before = m.updated_at
    client.post(
        f"/admin/members/{m.id}/subscribed",
        data={"subscribed": "1"},
        headers=_auth(),
        follow_redirects=False,
    )
    session.refresh(m)
    assert m.subscribed is True
    assert m.updated_at == before


def test_members_page_offers_restore_button(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _member(session, "끊긴회원", "gone@example.com")
    m.subscribed = False
    session.add(m)
    session.commit()
    body = client.get("/admin/members", headers=_auth()).text
    assert f'action="/admin/members/{m.id}/subscribed"' in body
    assert "되살리기" in body


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


# ------------------------------------------------------------------ 탭 4: 참여도 (T-019)


def _pilot(
    session: Session,
    name: str,
    *,
    group_no: int,
    org_type: str,
    stored_score: float = 0.0,
) -> Member:
    """파일럿 회원 1명 — pilot_members의 저장 점수는 일부러 0으로 둔다(AC5 검증용)."""
    m = _member(session, name, f"{name}@example.com")
    session.add(
        PilotMember(
            member_id=m.id,  # pyright: ignore[reportArgumentType]
            name=name,
            group_no=group_no,
            org_type=org_type,
            program="푸드테크 계약학과",
            activity_score=stored_score,
        )
    )
    session.commit()
    return m


def _sent_and_clicked(session: Session, m: Member, *, clicks: int) -> None:
    nl = Newsletter(subject="편", html_body="<p>x</p>", status="sent")
    session.add(nl)
    session.commit()
    session.refresh(nl)
    sent_at = datetime.now(UTC) - timedelta(days=1)
    session.add(
        SendLog(
            newsletter_id=nl.id,  # pyright: ignore[reportArgumentType]
            member_id=m.id,
            email=m.email or "",
            status="sent",
            created_at=sent_at,
        )
    )
    session.commit()
    for i in range(clicks):
        session.add(
            EngagementEvent(
                member_id=m.id,
                newsletter_id=nl.id,
                event_type="clicked",
                url=f"https://n/{m.id}/{i}",
                provider_event_id=f"k{m.id}-{i}",
                occurred_at=sent_at + timedelta(minutes=5 + i),
            )
        )
    session.commit()


def test_scores_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/scores").status_code == 401
    assert client.get("/admin/scores", headers=_auth("wrong")).status_code == 401


def test_scores_empty_state_does_not_break(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    resp = client.get("/admin/scores", headers=_auth())
    assert resp.status_code == 200
    assert "아직 참여도를 낼 회원이 없습니다" in resp.text


def test_scores_computed_live_not_from_stored_column(
    client: TestClient, session: Session, monkeypatch
):
    """AC5: pilot_members의 저장 점수가 0이어도 실제 참여가 있으면 0이 아닌 값이 나온다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    active = _pilot(session, "활발한사람", group_no=1, org_type="기관")
    quiet = _pilot(session, "잠잠한사람", group_no=2, org_type="개인")
    _sent_and_clicked(session, active, clicks=3)
    _sent_and_clicked(session, quiet, clicks=0)

    resp = client.get("/admin/scores", headers=_auth())
    assert resp.status_code == 200
    body = resp.text
    assert "활발한사람" in body and "잠잠한사람" in body
    # 저장값은 둘 다 0.0 — 화면 점수가 저장값을 그대로 읽었다면 0만 보여야 한다
    assert (
        session.exec(select(PilotMember).where(PilotMember.name == "활발한사람"))
        .one()
        .activity_score
        == 0.0
    )
    assert body.index("활발한사람") < body.index("잠잠한사람")  # 점수 내림차순
    assert "참여도 분포" in body and "회원별 참여도" in body


def test_scores_shows_segments_with_headcount(client: TestClient, session: Session, monkeypatch):
    """AC3: 세그먼트 평균은 인원 수와 함께 나온다 — n=1 평균이 오독되지 않게."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    m = _pilot(session, "그룹원", group_no=3, org_type="기관")
    _sent_and_clicked(session, m, clicks=2)

    body = client.get("/admin/scores", headers=_auth()).text
    assert "발송 그룹" in body and "소속 유형" in body and "프로그램" in body
    assert "3조" in body and "기관" in body
    assert "1명" in body  # 인원 수 병기


def test_scores_marks_never_sent_member_as_unknown(
    client: TestClient, session: Session, monkeypatch
):
    """AC: 발송 이력이 없는 회원은 '잠잠'이 아니라 '판단 보류'."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _pilot(session, "미발송회원", group_no=4, org_type="개인")

    body = client.get("/admin/scores", headers=_auth()).text
    # 안내 문구에도 등급 이름이 나오므로 칩 마크업으로 정확히 본다
    assert _tier_chip("unknown") in body
    assert _tier_chip("dormant") not in body


# ------------------------------------------------------------------ 탭 5: 발송 검토


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


# ------------------------------------------------------------------ 발송 설정 (T-014)


def _settings_body(**over: int) -> dict[str, str]:
    body = {"n_headlines": 2, "n_mains": 3, "n_domestic": 4, "n_overseas": 1, "days": 7}
    body.update(over)
    return {k: str(v) for k, v in body.items()}  # 폼 전송은 문자열


def test_review_shows_settings_form_with_current_values(client: TestClient, monkeypatch):
    """설정 행이 없어도 폼은 코드 기본값으로 그려진다 — 마이그레이션 직후 상태."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    page = client.get("/admin/review", headers=_auth())
    assert "발송 구성" in page.text
    assert 'name="n_mains" value="3"' in page.text
    assert 'name="n_domestic" value="4"' in page.text


def test_saved_settings_change_what_gets_assembled(
    client: TestClient, session: Session, monkeypatch
):
    """저장한 값이 실제 조립에 반영된다(AC4) — 국내만 3꼭지로 줄여본다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")  # 게이트 전량 통과
    _seed_diverse_news(session)  # 국내4 + 해외1

    saved = client.post(
        "/admin/review/settings",
        headers=_auth(),
        data=_settings_body(n_headlines=1, n_mains=2, n_domestic=3, n_overseas=0),
        follow_redirects=False,
    )
    assert saved.status_code == 303

    assert client.post("/admin/review/build", headers=_auth(), follow_redirects=False).status_code
    nl = session.exec(select(Newsletter)).one()
    assert "3선" in nl.subject  # 5선이 아니라 설정대로 3꼭지
    assert "GLOBAL" not in nl.html_body  # 해외 0건으로 지정했으므로 실리지 않는다


def test_invalid_settings_rejected_with_reason(client: TestClient, monkeypatch):
    """합이 안 맞으면 저장을 막고 사유를 돌려준다(AC5)."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    resp = client.post(
        "/admin/review/settings",
        headers=_auth(),
        data=_settings_body(n_domestic=2, n_overseas=1),  # 3 != 에피2+메인3
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "같아야 합니다" in resp.json()["detail"]


def test_root_and_admin_redirect_to_status(client: TestClient):
    """주소창에 도메인만 치면 "/"로 들어온다 — 404가 아니라 현황판으로 보내야 한다.

    2026-08-06 실사고: admin.foodtech-center.org를 열었더니 {"detail":"Not Found"}만 떴다.
    라우트가 /admin/* 뿐이라 루트가 비어 있었다.
    """
    for path in ("/", "/admin"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code in (307, 308), f"{path}가 리다이렉트하지 않는다"
        assert resp.headers["location"] == "/admin/status"
