from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Newsletter(SQLModel, table=True):
    """뉴스레터 캠페인."""

    __tablename__ = "newsletters"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    subject: str
    html_body: str
    text_body: str | None = None
    created_by: str | None = None  # admin email
    status: str = Field(default="draft", index=True)  # draft | sending | sent | failed
    # 세그먼트 조건 (예: {"program": "월드푸드테크협의회"}) — 발송 대상 재현 가능하게 보존
    target_filter: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    total_recipients: int = Field(default=0)
    sent_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
