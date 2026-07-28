from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class PilotMember(SQLModel, table=True):
    """파일럿(랩실) 전용 회원 스냅샷 + Activity Score 실험 테이블.

    members가 진실의 원천이고 여기는 member_id로 참조하는 25명 샌드박스.
    Activity Score 로직을 작은 테이블에서 자유롭게 실험하려고 컬럼을 넉넉히 둔다
    (발송·추적 집계, 분야별 관심, 점수·등급). 운영 members(3,413명)는 건드리지 않는다.
    """

    __tablename__ = "pilot_members"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="members.id", unique=True, index=True)

    # 프로필 스냅샷 (members에서 복사, 파일럿 기준 시점 보존)
    name: str
    email: str | None = Field(default=None, index=True)
    position: str | None = None

    # 세그먼트 (회원관리 필터용)
    program: str | None = Field(
        default=None, index=True
    )  # 협의회 / 최고책임자과정 / 사업화교육 / 계약학과
    org_type: str | None = Field(default=None, index=True)  # 기업 / 개인 / 기관
    organization: str | None = None
    group_no: int | None = Field(default=None, index=True)  # 파일럿 발송 그룹 1~5

    # 구독
    subscribed: bool = Field(default=True)
    unsubscribe_token: str | None = None

    # 발송·추적 집계 (engagement_events / send_logs에서 롤업)
    emails_sent: int = Field(default=0)
    emails_opened: int = Field(default=0)
    links_clicked: int = Field(default=0)
    last_sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_opened_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_clicked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # 분야별 관심 (Activity Score 원천 — {카테고리 슬러그: 횟수})
    category_clicks: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    category_opens: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )

    # Activity Score (아직 로직 미구현 — 컬럼만 선반영)
    activity_score: float = Field(default=0.0)
    activity_tier: str | None = Field(default=None, index=True)  # active / warm / dormant
    score_updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # 메타
    notes: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
