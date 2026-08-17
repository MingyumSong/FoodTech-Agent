"""T-027 2단계 — 04 Newsletter 데이터 API. 인증·집계 범위·PII 경계 검증."""

import base64
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.news_item import NewsItem
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog

TOKEN = "secret-token"


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _seed(session: Session) -> None:
    """회원 1명이 1편을 받고 열람·클릭까지 한 최소 시나리오."""
    now = datetime.now(UTC)
    m = Member(name="김참여", email="join@example.com", subscribed=True)
    session.add(m)
    nl = Newsletter(subject="편", html_body="<p>x</p>", target_filter={"program": "pilot-daily"})
    session.add(nl)
    session.add(
        NewsItem(
            title="기사",
            url="https://n/a",
            summary="s",
            origin="naver",
            region="domestic",
            category="convenience",
            collected_at=now,
        )
    )
    session.commit()
    session.refresh(m)
    session.refresh(nl)
    session.add(PilotMember(member_id=m.id, name=m.name))  # pyright: ignore[reportArgumentType]
    session.add(SendLog(newsletter_id=nl.id, member_id=m.id, email=m.email, status="sent"))  # pyright: ignore[reportArgumentType]
    for i, kind in enumerate(("opened", "clicked")):
        session.add(
            EngagementEvent(
                member_id=m.id,
                newsletter_id=nl.id,
                event_type=kind,
                url="https://n/a" if kind == "clicked" else None,
                provider_event_id=f"ev-{i}",
                occurred_at=now - timedelta(minutes=5 - i),
            )
        )
    session.commit()


def test_api_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/api/newsletter").status_code == 401
    assert client.get("/admin/api/newsletter", headers=_auth()).status_code == 200


def test_api_never_returns_email(client: TestClient, session: Session, monkeypatch):
    """TOP 10은 순위를 보는 곳이지 연락처를 보는 곳이 아니다.

    `collect_scores`는 CSV 내보내기 때문에 이메일을 함께 읽는다 — 그게 이 응답으로
    새어 나가면 안 된다. 명단이 필요하면 참여도 탭의 CSV를 쓴다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _seed(session)
    body = client.get("/admin/api/newsletter", headers=_auth()).text
    assert "join@example.com" not in body
    assert "@" not in body


def test_kpis_carry_their_scope(client: TestClient, session: Session, monkeypatch):
    """구독자는 전체 명단, 참여율은 파일럿 기준 — 범위가 다른 숫자가 한 줄에 놓인다.

    범위를 안 적으면 나란히 놓인 숫자가 거짓말을 한다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _seed(session)
    data = client.get("/admin/api/newsletter", headers=_auth()).json()
    labels = {k["label"]: k for k in data["kpis"]}
    assert labels["구독자"]["note"] == "전체 명단"
    assert "파일럿" in labels["열람률"]["note"]
    assert "파일럿" in labels["클릭률"]["note"]


def test_rate_is_null_not_zero_without_sends(client: TestClient, monkeypatch):
    """발송이 0이면 열람률은 0%가 아니라 '잴 수 없음'이다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    data = client.get("/admin/api/newsletter", headers=_auth()).json()
    rates = {k["label"]: k["value"] for k in data["kpis"]}
    assert rates["열람률"] is None
    assert rates["클릭률"] is None


def test_top_rows_carry_tier_key(client: TestClient, session: Session, monkeypatch):
    """화면이 색을 고를 땐 한글 라벨이 아니라 키를 쓴다 — 라벨이 바뀌어도 안 틀어지게."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _seed(session)
    data = client.get("/admin/api/newsletter", headers=_auth()).json()
    assert data["top"], "파일럿 회원이 있으면 순위가 나와야 한다"
    row = data["top"][0]
    assert row["tier_key"] in {"active", "warm", "dormant", "unknown", "unsubscribed"}
    assert row["tier"] != row["tier_key"]  # 라벨은 한글


def test_empty_database_does_not_break(client: TestClient, monkeypatch):
    """데이터가 하나도 없어도 200이어야 한다 — 랩실이 빈 DB로 화면을 열어본다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    data = client.get("/admin/api/newsletter", headers=_auth()).json()
    assert data["top"] == []
    assert data["categories"]["ranked"] == []
    assert len(data["kpis"]) == 4


def test_categories_use_korean_labels_not_slugs(client: TestClient, session: Session, monkeypatch):
    """분야는 한글로 나가야 한다 — collect_popular 는 슬러그(plant_based)를 돌려준다.

    기존 인기분야 탭과 같은 사전을 쓰는지도 함께 지킨다. 두 화면의 분야 이름이 갈라지면
    같은 데이터를 보고도 다른 이야기를 하게 된다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _seed(session)
    data = client.get("/admin/api/newsletter", headers=_auth()).json()
    labels = [c["label"] for c in data["categories"]["ranked"]]
    assert labels, "클릭이 매칭됐으면 분야가 나와야 한다"
    assert "간편식" in labels  # _seed 의 기사 category=convenience
    assert not any("_" in label for label in labels), f"슬러그가 그대로 나갔다: {labels}"
