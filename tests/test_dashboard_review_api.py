"""T-027 3b — 발송 검토 API. 가드·설정 검증·멱등 조립."""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import settings
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.news_item import NewsItem
from app.models.send_log import SendLog
from app.services.pilot_daily import (
    PILOT_PROGRAM,
    ROTATION_CATEGORIES,
    _todays_pilot_newsletter,
)

TOKEN = "secret-token"


@pytest.fixture(autouse=True)
def _no_real_send(monkeypatch):
    """발송 키를 지운다 — 가드가 깨지는 순간 이 테스트가 **진짜 메일을 보내는** 걸 막는다.

    가드를 검증하는 파일이라 가드가 실패하면 발송 경로가 열린다. 안전장치는 여기 있어야 한다.
    """
    monkeypatch.setattr(settings, "resend_api_key", "")


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _recipient(session: Session, email: str) -> None:
    m = Member(name="수신자", email=email, subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    session.add(MemberProgram(member_id=m.id, program=PILOT_PROGRAM))  # pyright: ignore[reportArgumentType]
    session.commit()


# 제목이 서로 닮으면 T-009 중복 병합이 삼켜서 풀이 말라버린다.
# "{분야} 기사 N" 같은 형태는 공통 어절 때문에 자카드 0.33이라 전부 한 덩어리가 된다.
_TITLES = "가나다 라마바 사아자 차카타 파하거 너더러 머버서 어저처".split()


def _news(session: Session) -> None:
    now = datetime.now(UTC)
    for i, cat in enumerate(ROTATION_CATEGORIES[:8]):
        session.add(
            NewsItem(
                title=_TITLES[i],
                url=f"https://n/{cat}/{i}",
                summary="요약 " * 40,
                source="테스트일보",
                origin="naver" if i < 5 else "brave",
                region="domestic" if i < 5 else "overseas",
                category=cat,
                published_at=now,
                collected_at=now,
            )
        )
    session.commit()


def test_review_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/api/review").status_code == 401


def test_cannot_send_without_an_edition(client: TestClient, session: Session, monkeypatch):
    """오늘 편이 없으면 발송 불가 — 이유가 문장으로 와야 화면이 설명할 수 있다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    _recipient(session, "a@example.com")

    d = client.get("/admin/api/review", headers=_auth()).json()
    assert d["can_send"] is False
    assert "조립" in d["blocked_reason"]

    res = client.post("/admin/api/review/send", headers=_auth())
    assert res.status_code == 400


def test_cannot_send_without_recipients(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _news(session)
    client.post("/admin/api/review/build", headers=_auth())

    d = client.get("/admin/api/review", headers=_auth()).json()
    assert d["can_send"] is False and d["recipients"] == 0
    assert "0명" in d["blocked_reason"]


def test_build_is_idempotent_and_reports_the_edition(
    client: TestClient, session: Session, monkeypatch
):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _news(session)
    _recipient(session, "b@example.com")

    first = client.post("/admin/api/review/build", headers=_auth()).json()
    assert first["edition"] is not None
    assert first["edition"]["items"] == 5
    assert first["can_send"] is True

    second = client.post("/admin/api/review/build", headers=_auth()).json()
    assert second["edition"]["id"] == first["edition"]["id"]  # 같은 날 재조립 없음


def test_invalid_settings_are_rejected_with_a_readable_reason(client: TestClient, monkeypatch):
    """저장 단계에서 막는다 — 조립 시점에 터지면 크론이 조용히 실패하고 그날 발송이 빠진다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    res = client.post(
        "/admin/api/review/settings",
        json={"n_headlines": 2, "n_mains": 3, "n_domestic": 9, "n_overseas": 9, "days": 7},
        headers=_auth(),
    )
    assert res.status_code == 400
    assert "같아야" in res.json()["detail"]


def test_settings_round_trip(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    res = client.post(
        "/admin/api/review/settings",
        json={"n_headlines": 1, "n_mains": 2, "n_domestic": 2, "n_overseas": 1, "days": 5},
        headers=_auth(),
    )
    assert res.status_code == 200
    s = res.json()["settings"]
    assert (s["n_headlines"], s["n_mains"], s["days"], s["total"]) == (1, 2, 5, 3)


def test_send_rechecks_the_guard_itself(client: TestClient, session: Session, monkeypatch):
    """화면이 '보낼 수 있다'고 판단했더라도 서버가 누르는 시점에 다시 본다.

    모달을 열어둔 사이 수신자가 0이 될 수 있다 — 그때 화면의 판단을 믿으면 안 된다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _news(session)
    m = Member(name="곧빠질사람", email="c@example.com", subscribed=True)
    session.add(m)
    session.commit()
    session.refresh(m)
    session.add(MemberProgram(member_id=m.id, program=PILOT_PROGRAM))  # pyright: ignore[reportArgumentType]
    session.commit()
    client.post("/admin/api/review/build", headers=_auth())
    assert client.get("/admin/api/review", headers=_auth()).json()["can_send"] is True

    # 화면은 그대로 둔 채 수신자가 사라진 상황
    m.subscribed = False
    session.add(m)
    session.commit()

    assert client.post("/admin/api/review/send", headers=_auth()).status_code == 400


def test_cannot_send_twice(client: TestClient, session: Session, monkeypatch):
    """이미 보낸 편은 다시 못 보낸다 (코드리뷰 지적, 2026-08-17).

    발송 루프가 수신자당 0.6초라 도는 도중 두 번째 클릭이 들어오면, 루프 시작 전에 뜬
    send_logs 스냅샷으로 판단하는 탓에 아직 안 보낸 사람에게 **중복 발송**된다.
    `(newsletter_id, email)` 유니크 제약도 없어 DB도 안 막는다. 서버 게이트가 1차 방어다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    _news(session)
    _recipient(session, "twice@example.com")
    client.post("/admin/api/review/build", headers=_auth())
    assert client.get("/admin/api/review", headers=_auth()).json()["can_send"] is True

    nl = _todays_pilot_newsletter(session)
    assert nl is not None and nl.id is not None
    nl_id = nl.id
    session.add(
        SendLog(newsletter_id=nl_id, member_id=None, email="twice@example.com", status="sent")
    )
    session.commit()

    d = client.get("/admin/api/review", headers=_auth()).json()
    assert d["can_send"] is False
    assert "이미" in d["blocked_reason"]
    assert client.post("/admin/api/review/send", headers=_auth()).status_code == 400
