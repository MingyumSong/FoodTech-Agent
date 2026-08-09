"""디저트 원클릭 반응 (T-013 AC7/AC8).

핵심 계약 두 가지: ① 같은 회원×같은 편은 몇 번을 눌러도 1행으로 수렴하고 마지막 값이 남는다.
② 토큰 없이는 남의 반응을 만들거나 바꿀 수 없다.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.engagement_event import EngagementEvent
from app.models.member import Member
from app.models.newsletter import Newsletter


def _member(session: Session, token: str, name: str = "반응자") -> Member:
    m = Member(name=name, email=f"{token}@example.com", subscribed=True, unsubscribe_token=token)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def _newsletter(session: Session) -> Newsletter:
    nl = Newsletter(subject="푸디픽 #013", html_body="<p></p>", text_body="", status="sent")
    session.add(nl)
    session.commit()
    session.refresh(nl)
    return nl


def _events(session: Session) -> list[EngagementEvent]:
    return list(
        session.exec(select(EngagementEvent).where(EngagementEvent.event_type == "reacted")).all()
    )


def test_reaction_is_recorded(client: TestClient, session: Session):
    m = _member(session, "tok-good")
    nl = _newsletter(session)

    resp = client.get(f"/reactions/tok-good/{nl.id}/good")
    assert resp.status_code == 200
    assert "좋았어요" in resp.text

    events = _events(session)
    assert len(events) == 1
    assert events[0].member_id == m.id
    assert events[0].newsletter_id == nl.id
    assert (events[0].payload or {})["reaction"] == "good"


def test_repeat_clicks_converge_to_last_value(client: TestClient, session: Session):
    """마음이 바뀌어 다시 눌러도 행이 쌓이지 않는다 — 멱등 키가 (회원, 편)이다."""
    _member(session, "tok-change")
    nl = _newsletter(session)

    for value in ("good", "bad", "ok"):
        assert client.get(f"/reactions/tok-change/{nl.id}/{value}").status_code == 200

    events = _events(session)
    assert len(events) == 1
    assert (events[0].payload or {})["reaction"] == "ok"


def test_page_tells_you_what_actually_changed(client: TestClient, session: Session):
    """화면이 매번 같은 말을 하면 수신자는 바뀐 줄 모르고 버튼을 계속 눌러본다.

    파일럿 수신자 피드백("버튼 하나 누르고 다른 버튼도 누를 수 있게 되어있음")의 실체가
    이것이다 — 기록은 멀쩡했고 화면이 결과를 안 비춰줬다.
    """
    _member(session, "tok-echo")
    nl = _newsletter(session)

    first = client.get(f"/reactions/tok-echo/{nl.id}/good").text
    assert "고맙습니다" in first

    same = client.get(f"/reactions/tok-echo/{nl.id}/good").text
    assert "이미 기록되어 있어요" in same

    changed = client.get(f"/reactions/tok-echo/{nl.id}/bad").text
    assert "바꿨습니다" in changed
    assert "좋았어요" in changed and "별로였어요" in changed  # 무엇에서 무엇으로

    assert len(_events(session)) == 1  # 그래도 행은 하나


def test_separate_editions_are_counted_separately(client: TestClient, session: Session):
    """편이 다르면 별개 반응이다 — 매일 발송이라 편별 추이가 지표가 된다."""
    _member(session, "tok-two")
    nl1, nl2 = _newsletter(session), _newsletter(session)

    client.get(f"/reactions/tok-two/{nl1.id}/good")
    client.get(f"/reactions/tok-two/{nl2.id}/bad")

    assert len(_events(session)) == 2


def test_unknown_token_is_rejected(client: TestClient, session: Session):
    nl = _newsletter(session)
    assert client.get(f"/reactions/nope-not-a-token/{nl.id}/good").status_code == 404
    assert _events(session) == []


def test_unknown_reaction_value_is_rejected(client: TestClient, session: Session):
    _member(session, "tok-bad-value")
    nl = _newsletter(session)
    assert client.get(f"/reactions/tok-bad-value/{nl.id}/awesome").status_code == 404
    assert _events(session) == []
