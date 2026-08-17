from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app.lib.errors import ConflictError, NotFoundError
from app.models.engagement_event import EngagementEvent
from app.models.member import Member, MemberCreate
from app.models.member_program import MemberProgram
from app.models.pilot_member import PilotMember
from app.models.send_log import SendLog


def list_members(
    session: Session,
    *,
    program: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Member]:
    query = select(Member).order_by(Member.id).limit(limit).offset(offset)  # pyright: ignore[reportArgumentType]
    if program is not None:
        program_member_ids = select(MemberProgram.member_id).where(MemberProgram.program == program)
        query = query.where(col(Member.id).in_(program_member_ids))
    return list(session.exec(query).all())


def get_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise NotFoundError(f"member {member_id} not found")
    return member


def create_member(session: Session, data: MemberCreate) -> Member:
    if data.email is not None:
        existing = session.exec(select(Member).where(Member.email == data.email)).first()
        if existing is not None:
            raise ConflictError(f"email {data.email} already exists")
    member = Member.model_validate(data)
    session.add(member)
    session.flush()  # member.id 확보
    if data.program is not None:
        assert member.id is not None
        session.add(MemberProgram(member_id=member.id, program=data.program, cohort=data.cohort))
    session.commit()
    session.refresh(member)
    return member


def set_subscribed(session: Session, member: Member, *, subscribed: bool) -> bool:
    """구독 상태를 바꾼다. **실제로 바뀐 경우에만** True를 돌려주고 `updated_at`을 남긴다 (T-025).

    수신거부·재구독이 한 곳을 지나게 해서 두 가지를 보장한다:
    - 멱등 — 같은 값으로 다시 불러도 아무 일도 안 일어난다(로그도 안 남는다).
    - 시각 기록 — 예전엔 `subscribed`만 바꾸고 `updated_at`을 안 건드려서 "언제 끊겼나"를
      알 수 없었다. 실제로 회원 3995의 이탈 시점을 3주나 잘못 읽었다.
    """
    if member.subscribed == subscribed:
        return False
    member.subscribed = subscribed
    member.updated_at = datetime.now(UTC)
    session.add(member)
    session.commit()
    return True


def set_program(session: Session, member: Member, program: str, *, joined: bool) -> bool:
    """회원을 프로그램에 넣거나 뺀다. 실제로 바뀐 경우에만 True (T-027 3a).

    발송 대상은 `_recipients`가 프로그램으로 고르므로, **이게 "발송 리스트에 넣는다"의 실체**다.
    지금까지 관리자 화면엔 이 기능이 없어서 — 회원 추가·삭제·구독 토글은 되는데 이미 있는
    회원을 발송 대상에 넣을 수가 없었다 — 요청이 올 때마다 스크립트를 돌려야 했다
    (2026-08-17 교수님을 pilot-daily에 넣어달라는 요청이 그랬다).

    구독 여부와는 별개다: 프로그램에 넣어도 `subscribed=False`면 발송되지 않는다.
    둘을 한 버튼으로 묶지 않는 이유는 뜻이 다르기 때문이다 —
    프로그램은 "어느 명단에 속하는가", 구독은 "메일을 받겠는가"다.
    """
    assert member.id is not None
    existing = session.exec(
        select(MemberProgram).where(
            MemberProgram.member_id == member.id, MemberProgram.program == program
        )
    ).first()

    if joined and existing is None:
        session.add(MemberProgram(member_id=member.id, program=program))
    elif not joined and existing is not None:
        session.delete(existing)
    else:
        return False

    session.commit()
    return True


def delete_member(session: Session, member_id: int) -> None:
    """회원 하드 삭제. FK 무결성을 지키려고 참조 행을 먼저 정리한다.

    - member_programs·pilot_members: 함께 삭제(회원에 종속된 데이터).
    - send_logs·engagement_events: member_id만 NULL로 분리(발송·추적 감사 기록은 보존).
    """
    member = session.get(Member, member_id)
    if member is None:
        raise NotFoundError(f"member {member_id} not found")

    for log in session.exec(select(SendLog).where(SendLog.member_id == member_id)).all():
        log.member_id = None
        session.add(log)
    for ev in session.exec(
        select(EngagementEvent).where(EngagementEvent.member_id == member_id)
    ).all():
        ev.member_id = None
        session.add(ev)
    for pm in session.exec(select(PilotMember).where(PilotMember.member_id == member_id)).all():
        session.delete(pm)
    for mp in session.exec(select(MemberProgram).where(MemberProgram.member_id == member_id)).all():
        session.delete(mp)
    session.flush()  # 자식(참조) 행 DELETE를 부모보다 먼저 확정 — FK 위반 방지
    session.delete(member)
    session.commit()
