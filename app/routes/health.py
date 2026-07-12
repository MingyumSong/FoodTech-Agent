from fastapi import APIRouter, Response
from sqlalchemy import text

from app.db import engine
from app.lib.logger import get_logger

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
