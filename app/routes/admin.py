"""관리자 페이지 — 현황판(T-010, 읽기 전용) + 회원관리·인기분야·발송검토(T-012).

매직링크 로그인 전 임시 인증: HTTP Basic (사용자명 admin, 비밀번호 = ADMIN_TOKEN).
브라우저 기본 암호창으로 접근 가능해야 해서 Bearer 헤더 대신 Basic을 쓴다.
회원 관리 탭은 관리 목적상 PII를 화면에 표시하되 로그·커밋엔 남기지 않는다(C6).
쓰기(회원 추가/삭제·발송)도 당분간 Basic — 매직링크는 후속 티켓.
"""

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.lib.errors import ConflictError, NotFoundError
from app.lib.logger import get_logger
from app.models.member import MemberCreate
from app.services.admin_pages import (
    _nav,
    collect_members_page,
    collect_popular,
    collect_review,
    render_members_page,
    render_popular_page,
    render_review_page,
)
from app.services.admin_status import collect_stats, render_status
from app.services.members import create_member, delete_member
from app.services.newsletter import PILOT_MAX_RECIPIENTS, UNSUB_PLACEHOLDER, _recipients
from app.services.pilot_daily import (
    PILOT_PROGRAM,
    _todays_pilot_newsletter,
    build_pilot_daily,
    send_reviewed,
)

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("admin")
_basic = HTTPBasic()


def require_admin_basic(credentials: HTTPBasicCredentials = Depends(_basic)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN not configured")
    ok_user = secrets.compare_digest(credentials.username, "admin")
    ok_pass = secrets.compare_digest(credentials.password, settings.admin_token)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


# ------------------------------------------------------------------ 현황판 (T-010)


@router.get("/status", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_status(session: Session = Depends(get_session)) -> str:
    return render_status(collect_stats(session), nav=_nav("/admin/status"))


# ------------------------------------------------------------------ 탭 1: 회원 관리


@router.get("/members", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_members(
    program: str | None = Query(default=None),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> str:
    data = collect_members_page(session, program=program, category=category, q=q, page=page)
    return render_members_page(data)


@router.post("/members", dependencies=[Depends(require_admin_basic)])
def admin_members_add(
    name: str = Form(...),
    email: str = Form(default=""),
    category: str = Form(default=""),
    organization: str = Form(default=""),
    position: str = Form(default=""),
    program: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    data = MemberCreate(
        name=name.strip(),
        email=email.strip() or None,
        category=category.strip() or None,
        organization=organization.strip() or None,
        position=position.strip() or None,
        program=program.strip() or None,
    )
    try:
        create_member(session, data)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("admin member added")  # PII는 로그에 남기지 않는다
    return RedirectResponse("/admin/members", status_code=303)


@router.post("/members/{member_id}/delete", dependencies=[Depends(require_admin_basic)])
def admin_members_delete(
    member_id: int, session: Session = Depends(get_session)
) -> RedirectResponse:
    try:
        delete_member(session, member_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info(f"admin member deleted: id={member_id}")
    return RedirectResponse("/admin/members", status_code=303)


# ------------------------------------------------------------------ 탭 2: 인기 분야


@router.get("/popular", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_popular(session: Session = Depends(get_session)) -> str:
    return render_popular_page(collect_popular(session))


# ------------------------------------------------------------------ 탭 4: 발송 검토


@router.get("/review", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_review(session: Session = Depends(get_session)) -> str:
    return render_review_page(collect_review(session))


@router.post("/review/build", dependencies=[Depends(require_admin_basic)])
def admin_review_build(session: Session = Depends(get_session)) -> RedirectResponse:
    """오늘 편 조립(멱등) — GET이 아니라 명시적 POST에서만 LLM 게이트·초안 생성이 일어난다."""
    try:
        build_pilot_daily(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/admin/review", status_code=303)


@router.get(
    "/review/preview", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)]
)
def admin_review_preview(session: Session = Depends(get_session)) -> str:
    nl = _todays_pilot_newsletter(session)
    if nl is None:
        raise HTTPException(status_code=404, detail="오늘 편이 없습니다 — 먼저 조립하세요")
    return nl.html_body.replace(UNSUB_PLACEHOLDER, "#")


@router.post("/review/send", dependencies=[Depends(require_admin_basic)])
def admin_review_send(
    background: BackgroundTasks, session: Session = Depends(get_session)
) -> RedirectResponse:
    """검토한 오늘 편을 지금 발송 — 가드 통과 후 백그라운드 발송+롤업. 멱등(이미 sent 스킵)."""
    nl = _todays_pilot_newsletter(session)
    if nl is None:
        raise HTTPException(status_code=400, detail="오늘 편이 없습니다 — 먼저 조립하세요")
    n = len(_recipients(session, PILOT_PROGRAM))
    if not 1 <= n <= PILOT_MAX_RECIPIENTS:
        raise HTTPException(
            status_code=400, detail=f"수신자 {n}명 — 발송 가드(1~{PILOT_MAX_RECIPIENTS}) 밖"
        )
    assert nl.id is not None
    background.add_task(send_reviewed, nl.id)
    logger.info(f"admin manual send accepted: newsletter_id={nl.id} recipients={n}")
    return RedirectResponse("/admin/review", status_code=303)
