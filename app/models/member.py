from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class MemberBase(SQLModel):
    name: str = Field(index=True)
    # 실명단에 이메일 결측(~6%)·중복이 존재 — unique 금지, 병합은 임포트 소관 (T-002)
    email: str | None = Field(default=None, index=True)
    phone: str | None = None

    # 실명단 매핑: 구분4→category, 구분5→subcategory, 구분3→membership_type
    category: str | None = Field(default=None, index=True)
    subcategory: str | None = None
    position: str | None = None
    organization: str | None = None
    location: str | None = None
    division: str | None = None
    business_area: str | None = None

    membership_status: str | None = Field(default=None, index=True)
    membership_type: str | None = None
    payment_history: str | None = None
    benefit_pct: str | None = None
    council_label: str | None = None

    subscribed: bool = Field(default=True)
    notes: str | None = None


class Member(MemberBase, table=True):
    __tablename__ = "members"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    unsubscribe_token: str | None = Field(default=None, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class MemberCreate(MemberBase):
    # 프로그램 소속은 member_programs 행으로 기록된다 (회원↔프로그램 M:N)
    program: str | None = None
    cohort: str | None = None


class MemberRead(MemberBase):
    id: int
    created_at: datetime
