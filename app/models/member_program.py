from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


class MemberProgram(SQLModel, table=True):
    """회원↔프로그램 M:N. 실명단이 사람×프로그램 1행 구조라 단일 컬럼로는 불가.

    기수(cohort)는 프로그램에 딸린 속성이므로 여기 둔다 (T-002).
    """

    __tablename__ = "member_programs"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("member_id", "program", name="uq_member_programs_member_program"),
    )

    id: int | None = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="members.id", index=True)
    # 실명단 구분1: 사업화교육 / 최고책임자과정 / 푸드테크학과 / 월드푸드테크협의회
    program: str = Field(index=True)
    cohort: str | None = None  # 구분2: 원우(N기) 등
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
