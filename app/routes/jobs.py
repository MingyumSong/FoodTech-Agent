from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.lib.logger import get_logger
from app.services.news import refresh_news_cache
from app.services.newsletter import build_newsletter, send_newsletter
from app.services.pilot_daily import pilot_send_status, run_pilot_daily

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


@router.post("/pilot-daily-send", dependencies=[Depends(require_jobs_token)])
def pilot_daily_send(background: BackgroundTasks) -> dict[str, str]:
    """파일럿 매일발송 (T-011) — 조립→발송→통계 롤업을 백그라운드로 넘기고 즉시 응답 (C4).

    잡 본체는 서비스 함수(run_pilot_daily)가 자체 세션·클라이언트로 수행한다.
    멱등: 같은 날 재호출 시 편을 재사용하고 이미 sent인 수신자는 스킵한다.
    뉴스 부족 등으로 조립이 실패하면 백그라운드에서 로그로 신호(발송은 일어나지 않음).
    """
    logger.info("jobs/pilot-daily-send triggered")
    background.add_task(run_pilot_daily)
    return {"job": "pilot-daily-send", "status": "accepted"}


@router.get("/pilot-daily-status", dependencies=[Depends(require_jobs_token)])
def pilot_daily_status() -> dict[str, object]:
    """오늘 편이 실제로 발송됐는지 (T-028) — 크론이 트리거 뒤에 이걸로 결과를 확인한다.

    트리거(202)는 "수락됐다"까지만 뜻한다. 조립이 실패하면 발송이 통째로 빠지는데도
    크론은 초록불이었다. 판정은 서비스가 하고 여기선 HTTP만 — 발송 현황은 회원 명단과
    달리 PII가 아니지만, 운영 정보라 JOBS_TOKEN 뒤에 둔다.
    """
    return pilot_send_status()
