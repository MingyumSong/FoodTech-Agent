from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class AppSetting(SQLModel, table=True):
    """운영 중 바꾸는 설정의 저장소 — key 하나에 JSONB 값 하나 (T-014).

    설정마다 컬럼을 늘리면 항목이 하나 생길 때마다 마이그레이션이 필요하다.
    발송 꼭지 수처럼 파일럿 동안 자주 만질 값들이라 key/value로 둔다.

    **행이 없는 상태가 정상이다** — 읽는 쪽이 코드 기본값으로 폴백해야 한다
    (마이그레이션 직후에도 발송이 멈추면 안 된다).
    """

    __tablename__ = "app_settings"  # pyright: ignore[reportAssignmentType]

    key: str = Field(primary_key=True)
    value: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
