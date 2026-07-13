from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from app.config import settings
from app.lib.logger import get_logger
from app.services.news import refresh_news_cache

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger("jobs")


def require_jobs_token(authorization: str = Header(default="")) -> None:
    if not settings.jobs_token:
        raise HTTPException(status_code=503, detail="JOBS_TOKEN not configured")
    if authorization != f"Bearer {settings.jobs_token}":
        raise HTTPException(status_code=401, detail="invalid jobs token")


@router.post("/ping", dependencies=[Depends(require_jobs_token)])
def ping() -> dict[str, str]:
    logger.info("jobs/ping triggered")
    return {"job": "ping", "status": "ok"}


@router.post("/news-refresh", dependencies=[Depends(require_jobs_token)])
def news_refresh(background: BackgroundTasks) -> dict[str, str]:
    """뉴스 캐시 갱신 — 수집(수십 초)은 백그라운드로 넘기고 즉시 응답한다 (C4).

    멱등: 재실행해도 캐시 파일을 다시 쓸 뿐이다. 결과 확인은 GET /health/news.
    """
    logger.info("jobs/news-refresh triggered")
    background.add_task(refresh_news_cache)
    return {"job": "news-refresh", "status": "accepted"}
