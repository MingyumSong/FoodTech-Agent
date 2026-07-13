from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db import engine
from app.lib.logger import get_logger
from app.services.news import check_news_health

router = APIRouter(tags=["ops"])
logger = get_logger("health")


@router.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        logger.error(f"health check failed: {exc}")
        response.status_code = 503
        return {"status": "degraded", "db": "unreachable"}


@router.get("/health/news")
def health_news(response: Response) -> dict[str, Any]:
    """뉴스 캐시 헬스체크 — 발송 전 크론이 먼저 호출해 기준 미달이면 발송을 중단한다."""
    report = check_news_health()
    if not report["ok"]:
        logger.warning(f"news health check failed: {report.get('reason')}")
        response.status_code = 503
    return report
