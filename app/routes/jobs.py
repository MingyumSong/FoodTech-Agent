from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.lib.logger import get_logger

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
