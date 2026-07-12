from sqlmodel import Session, col, select

from app.lib.errors import ConflictError, NotFoundError
from app.models.member import Member, MemberCreate
from app.models.member_program import MemberProgram


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
