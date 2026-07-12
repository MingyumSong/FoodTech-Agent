from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class SendLog(SQLModel, table=True):
    """캠페인×회원 발송 1건의 결과. 열람·클릭은 engagement_events 소관."""

    __tablename__ = "send_logs"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    newsletter_id: int = Field(foreign_key="newsletters.id", index=True)
    member_id: int | None = Field(default=None, foreign_key="members.id", index=True)
    email: str = Field(index=True)
    status: str = Field(default="queued", index=True)  # queued | sent | failed | bounced
    # Resend 메시지 ID — 웹훅 페이로드의 email_id로 이벤트를 역추적하는 조인 키
    provider_id: str | None = Field(default=None, unique=True)
    error: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
