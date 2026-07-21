from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.lib.logger import get_logger
from app.services.news import refresh_news_cache
from app.services.newsletter import build_newsletter, send_newsletter

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


@router.post("/newsletter-build", dependencies=[Depends(require_jobs_token)])
def newsletter_build(
    program: str = Query(description="세그먼트 프로그램명 (예: pilot-lab)"),
    days: int = Query(default=7, ge=1, le=30),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """푸디픽 초안 생성 — 같은 날 같은 세그먼트는 기존 초안 재사용(멱등). 발송은 하지 않는다."""
    logger.info("jobs/newsletter-build triggered")
    try:
        nl = build_newsletter(session, program=program, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": "newsletter-build", "newsletter_id": nl.id, "subject": nl.subject}


@router.post("/newsletter-send", dependencies=[Depends(require_jobs_token)])
def newsletter_send(
    background: BackgroundTasks,
    newsletter_id: int = Query(description="newsletter-build가 반환한 id"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """발송 — 장시간 작업이라 백그라운드로 넘기고 즉시 응답 (C4).

    멱등: 재호출 시 이미 sent인 수신자는 send_logs 기준으로 건너뛴다.
    가드(수신자 상한·세그먼트 부재)는 수락 전에 검증해 400으로 거절한다.
    """
    logger.info("jobs/newsletter-send triggered")
    from app.models.newsletter import Newsletter
    from app.services.newsletter import PILOT_MAX_RECIPIENTS, _recipients

    nl = session.get(Newsletter, newsletter_id)
    if nl is None:
        raise HTTPException(status_code=404, detail="newsletter 없음")
    program = (nl.target_filter or {}).get("program")
    if not program:
        raise HTTPException(status_code=400, detail="target_filter.program 없음")
    n = len(_recipients(session, program))
    if n > PILOT_MAX_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"수신자 {n}명 > 상한 {PILOT_MAX_RECIPIENTS}")

    background.add_task(send_newsletter, newsletter_id)  # 자체 세션으로 실행
    return {"job": "newsletter-send", "status": "accepted", "recipients": n}
