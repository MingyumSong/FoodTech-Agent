"""T-023 Activity Score 활용 — 등급 기반 명단 추출·발송 대상 선정.

핵심 회귀 방어: 등급을 안 주면 수신자 목록이 **기존과 완전히 동일**해야 한다.
등급 필터는 목록을 좁히기만 하므로 100명 가드·멱등을 건드리면 안 된다.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.models.newsletter import Newsletter
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog
from app.services.admin_pages import scores_csv
from app.services.newsletter import _recipients, build_newsletter, send_newsletter
from tests.test_admin_pages import TOKEN, _auth
from tests.test_newsletter import DISTINCT_TITLES, PROGRAM, _seed_news

ACTIVE, DORMANT = "활발회원", "잠잠회원"


def _id(value: int | None) -> int:
    assert value is not None
    return value


def _member(session: Session, name: str, email: str) -> Member:
    m = Member(name=name, email=email, subscribed=True, unsubscribe_token=f"tok-{email}")
    session.add(m)
    session.commit()
    session.refresh(m)
    session.add(MemberProgram(member_id=_id(m.id), program=PROGRAM))
    session.commit()
    return m


def _newsletter(session: Session, subject: str) -> Newsletter:
    nl = Newsletter(subject=subject, html_body="<p>x</p>", target_filter={"program": PROGRAM})
    session.add(nl)
    session.commit()
    session.refresh(nl)
    return nl


def _seed_engagement(session: Session) -> tuple[Member, Member]:
    """활발 1명 + 잠잠 1명. 발송 4편 중 활발은 전편 클릭, 잠잠은 무반응."""
    active = _member(session, ACTIVE, "active@example.com")
    dormant = _member(session, DORMANT, "dormant@example.com")
    now = datetime.now(UTC)
    for i in range(4):
        nl = _newsletter(session, f"편 {i}")
        sent_at = now - timedelta(days=i)
        for m in (active, dormant):
            session.add(
                SendLog(
                    newsletter_id=_id(nl.id),
                    member_id=m.id,
                    email=m.email or "",
                    status="sent",
                    created_at=sent_at,
                )
            )
        # 활발 회원만 클릭 — 봇 구간(10초)을 넘겨 사람 행동으로 기록
        session.add(
            EngagementEvent(
                provider_event_id=f"click-{i}",
                member_id=active.id,
                newsletter_id=nl.id,
                event_type="clicked",
                url=f"https://news.example.com/{i}",
                occurred_at=sent_at + timedelta(minutes=5),
            )
        )
    session.commit()
    return active, dormant


def test_ac6_no_tiers_keeps_recipients_identical(session: Session):
    """AC6 회귀: 등급을 안 주면 기존 동작 그대로 — 점수 계산도 개입하지 않는다."""
    active, dormant = _seed_engagement(session)
    everyone = _recipients(session, PROGRAM)
    assert {m.email for m in everyone} == {active.email, dormant.email}
    assert _recipients(session, PROGRAM, tiers=None) == everyone
    assert _recipients(session, PROGRAM, tiers=[]) == everyone  # 빈 목록도 "전원"


def test_tier_filter_narrows_recipients(session: Session):
    """등급을 주면 그 등급 회원만 남는다."""
    active, dormant = _seed_engagement(session)
    picked = _recipients(session, PROGRAM, tiers=["active"])
    assert [m.email for m in picked] == [active.email]

    picked = _recipients(session, PROGRAM, tiers=["dormant"])
    assert [m.email for m in picked] == [dormant.email]

    both = _recipients(session, PROGRAM, tiers=["active", "dormant"])
    assert {m.email for m in both} == {active.email, dormant.email}


def test_tier_filter_keeps_base_conditions(session: Session):
    """등급 필터가 구독 해지자를 되살리지 않는다 — 기존 조건은 그대로 적용된다."""
    active, _ = _seed_engagement(session)
    active.subscribed = False
    session.add(active)
    session.commit()
    assert _recipients(session, PROGRAM, tiers=["active"]) == []


def test_ac5_send_respects_target_filter_tiers(session: Session, monkeypatch):
    """AC5: tiers를 담은 발송은 해당 등급에게만 간다 — 다른 등급은 send_logs에 안 남는다."""
    monkeypatch.setattr(settings, "resend_api_key", "")  # 드라이런 — 실제 발송 API를 안 탄다
    active, dormant = _seed_engagement(session)
    _seed_news(session)
    nl = build_newsletter(session, program=PROGRAM, tiers=["active"])
    assert nl.target_filter is not None
    assert nl.target_filter["tiers"] == ["active"]
    assert nl.target_filter["member_ids"] == [active.id]  # 대상은 조립 때 확정

    stats = send_newsletter(nl.id or 0, session=session)
    assert stats["recipients"] == 1
    emails = [
        log.email
        for log in session.exec(select(SendLog).where(SendLog.newsletter_id == nl.id)).all()
    ]
    assert emails == [active.email]
    assert dormant.email not in emails


def test_ac7_idempotent_with_tiers(session: Session, monkeypatch):
    """AC7: 등급으로 좁혀도 재발송은 멱등 — 두 번째 호출은 전부 skipped."""
    monkeypatch.setattr(settings, "resend_api_key", "")  # 드라이런
    _seed_engagement(session)
    _seed_news(session)
    nl = build_newsletter(session, program=PROGRAM, tiers=["active"])
    first = send_newsletter(nl.id or 0, session=session)
    second = send_newsletter(nl.id or 0, session=session)
    assert first["sent"] == 1 and second["sent"] == 0 and second["skipped"] == 1


def test_sending_does_not_shrink_its_own_audience(session: Session, monkeypatch):
    """회귀: 발송이 자기 수신자 목록을 바꾸면 안 된다.

    실측 사고 — 등급을 발송 시점에 계산했더니, 첫 발송이 `send_logs`에 무반응 1건을 더해
    점수가 떨어져 **재시도에서 대상이 1명 → 0명**이 됐다. 중간에 실패하면 받아야 할 사람이
    영영 빠진다. 대상은 조립 시점에 확정한다.
    """
    monkeypatch.setattr(settings, "resend_api_key", "")
    active, _ = _seed_engagement(session)
    _seed_news(session)
    nl = build_newsletter(session, program=PROGRAM, tiers=["active"])

    send_newsletter(nl.id or 0, session=session)
    # 발송으로 무반응 1건이 쌓여 지금 다시 계산하면 등급이 달라진다 — 그래도 대상은 그대로여야 한다
    again = send_newsletter(nl.id or 0, session=session)
    assert again["recipients"] == 1, "재시도에서 대상이 사라졌다"
    assert again["skipped"] == 1
    logs = session.exec(select(SendLog).where(SendLog.newsletter_id == nl.id)).all()
    assert [log.email for log in logs] == [active.email]


def test_unsubscribed_after_build_is_still_excluded(session: Session, monkeypatch):
    """대상을 얼려도 수신거부는 발송 시점에 다시 확인한다 — 얼린 목록이 해지를 무시하면 안 된다."""
    monkeypatch.setattr(settings, "resend_api_key", "")
    active, _ = _seed_engagement(session)
    _seed_news(session)
    nl = build_newsletter(session, program=PROGRAM, tiers=["active"])

    active.subscribed = False
    session.add(active)
    session.commit()

    stats = send_newsletter(nl.id or 0, session=session)
    assert stats["recipients"] == 0
    assert session.exec(select(SendLog).where(SendLog.newsletter_id == nl.id)).all() == []


def test_draft_with_different_tiers_is_not_reused(session: Session):
    """대상 등급이 다르면 다른 초안이다 — 재사용하면 옛 대상에게 나간다."""
    _seed_engagement(session)
    _seed_news(session)
    all_draft = build_newsletter(session, program=PROGRAM)
    active_draft = build_newsletter(session, program=PROGRAM, tiers=["active"])
    assert all_draft.id != active_draft.id
    # 같은 등급이면 재사용(멱등)
    assert build_newsletter(session, program=PROGRAM, tiers=["active"]).id == active_draft.id


# ---- CSV 명단 추출 -----------------------------------------------------------------


def _seed_pilot_rows(session: Session) -> None:
    for m in session.exec(select(Member)).all():
        session.add(PilotMember(member_id=_id(m.id), name=m.name, program=PROGRAM))
    session.commit()


def test_ac1_csv_has_identity_and_score_columns(session: Session):
    """AC1: 이름·이메일·점수·등급·백분위·발송수·참여수가 들어간다."""
    _seed_engagement(session)
    _seed_pilot_rows(session)
    body = scores_csv(session)
    header = body.splitlines()[0]
    for column in ("이름", "이메일", "점수", "등급", "백분위", "발송수", "참여수"):
        assert column in header
    assert "active@example.com" in body
    assert ACTIVE in body


def test_ac2_csv_tier_filter(session: Session):
    """AC2: 등급으로 거를 수 있고, 안 주면 전원이 나온다."""
    _seed_engagement(session)
    _seed_pilot_rows(session)

    everyone = scores_csv(session)
    assert ACTIVE in everyone and DORMANT in everyone

    only_active = scores_csv(session, tiers=["active"])
    assert ACTIVE in only_active
    assert DORMANT not in only_active


def test_ac4_csv_has_utf8_bom(session: Session):
    """AC4: BOM이 없으면 Excel이 한글 이름을 깨뜨린다."""
    _seed_engagement(session)
    _seed_pilot_rows(session)
    body = scores_csv(session)
    assert body.startswith("﻿")
    assert body.encode("utf-8").startswith(b"\xef\xbb\xbf")


def test_csv_is_empty_but_valid_when_no_members(session: Session):
    """회원이 없어도 머리글은 나온다 — 빈 파일이 아니라 빈 표."""
    body = scores_csv(session)
    assert "이메일" in body
    assert len([ln for ln in body.splitlines() if ln.strip()]) == 1


def test_ac3_csv_requires_auth(client: TestClient, monkeypatch):
    """AC3: 인증 없이는 PII가 나가지 않는다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/scores.csv").status_code == 401
    assert client.get("/admin/scores.csv", headers=_auth("wrong")).status_code == 401


@pytest.mark.parametrize("query", ["", "?tier=active", "?tier=active&tier=warm"])
def test_csv_route_returns_attachment(client: TestClient, monkeypatch, query: str):
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    resp = client.get(f"/admin/scores.csv{query}", headers=_auth())
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]


def test_titles_fixture_is_shared_not_duplicated():
    """뉴스 픽스처를 test_newsletter에서 가져다 쓴다 — 제목이 겹치면 큐레이션이 병합한다."""
    assert len(set(DISTINCT_TITLES)) == len(DISTINCT_TITLES)
