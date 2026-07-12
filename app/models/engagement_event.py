from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class EngagementEvent(SQLModel, table=True):
    """참여 이벤트 — Resend 웹훅(open/click/bounce 등) 적재. 대용량 전제.

    send_log/member/newsletter FK를 수신 시점에 모두 해석해 저장한다:
    Activity Score가 회원×이벤트 조인이므로 의도적 비정규화 (T-002).
    """

    __tablename__ = "engagement_events"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("ix_engagement_events_member_occurred", "member_id", "occurred_at"),
        Index("ix_engagement_events_newsletter_type", "newsletter_id", "event_type"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    send_log_id: int | None = Field(default=None, foreign_key="send_logs.id", index=True)
    member_id: int | None = Field(default=None, foreign_key="members.id")
    newsletter_id: int | None = Field(default=None, foreign_key="newsletters.id")
    # delivered | opened | clicked | bounced | complained | unsubscribed
    event_type: str = Field(index=True)
    url: str | None = None  # click 이벤트의 클릭된 URL — 뉴스별 집계 근거
    # 웹훅 재시도로 같은 이벤트가 중복 도착하는 게 정상 — unique로 멱등 처리
    provider_event_id: str | None = Field(default=None, unique=True)
    payload: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    occurred_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )  # 웹훅이 알려준 발생 시각
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )  # 우리가 적재한 시각
