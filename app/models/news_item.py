from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class NewsItem(SQLModel, table=True):
    """LLM 분류를 거쳐 저장된 뉴스 — 발송 조회·클릭 집계의 원본 (T-006).

    category는 LLM 분류 슬러그(정부 10대 + general). "해당없음"은 저장하지 않는다.
    수집 검색어 분야(캐시의 category)와 다른 개념이므로 혼동 주의.
    """

    __tablename__ = "news_items"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    title: str
    url: str = Field(unique=True, index=True)  # 멱등 키 — 클릭 이벤트 url과 문자열 매칭
    summary: str = ""
    source: str = ""  # 매체명 (예: 식품음료신문)
    origin: str = ""  # 수집 경로: naver | brave | rss | google_news
    region: str = ""  # domestic | overseas
    category: str = Field(index=True)  # LLM 분류 슬러그 (news_classify.SLUG_BY_KO)
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
