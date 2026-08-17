"""관리자 페이지 — 현황판(T-010) + 회원관리·인기분야·발송검토(T-012)
+ 참여도(T-019) + 명단 CSV 내보내기(T-023).

매직링크 로그인 전 임시 인증: HTTP Basic (사용자명 admin, 비밀번호 = ADMIN_TOKEN).
브라우저 기본 암호창으로 접근 가능해야 해서 Bearer 헤더 대신 Basic을 쓴다.
회원 관리 탭은 관리 목적상 PII를 화면에 표시하되 로그·커밋엔 남기지 않는다(C6).
쓰기(회원 추가/삭제·발송)도 당분간 Basic — 매직링크는 후속 티켓.
"""

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Form, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.lib.errors import ConflictError, NotFoundError
from app.lib.logger import get_logger
from app.models.member import Member, MemberCreate
from app.services.admin_pages import (
    TIER_ORDER,
    _nav,
    collect_members_page,
    collect_popular,
    collect_review,
    collect_scores,
    render_members_page,
    render_popular_page,
    render_review_page,
    render_scores_page,
    scores_csv,
)
from app.services.admin_status import collect_stats, render_status
from app.services.dashboard_api import members_page, newsletter_section, review_panel
from app.services.members import (
    create_member,
    delete_member,
    get_member,
    set_program,
    set_subscribed,
)
from app.services.newsletter import PILOT_MAX_RECIPIENTS, UNSUB_PLACEHOLDER, _recipients
from app.services.pilot_daily import (
    PILOT_PROGRAM,
    _todays_pilot_newsletter,
    build_pilot_daily,
    send_reviewed,
)
from app.services.send_settings import SendSettings, save_send_settings

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


# ------------------------------------------------------------------ 대시보드 셸 (T-027)

# 템플릿은 `app/static/` 밖에 둔다 — static은 공개 마운트라 거기 두면 인증을 우회한다.
# CSS·JS는 데이터가 없어 공개로 둬도 무방하고, 실제 숫자는 전부 인증된 API에서만 나온다.
_DASHBOARD_HTML = Path(__file__).resolve().parents[1] / "templates" / "dashboard.html"


@router.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_dashboard() -> str:
    """푸드테크 대시보드 — 4섹션 셸. 섹션 본문은 브라우저가 JSON API로 받아 그린다 (T-027).

    페이지 전체가 인증 뒤에 있다(결정 5, 안 1) — 회원 명단과 발송 실행이 한 화면에 있어서
    공개 구역을 두지 않는다. 새 섹션을 추가하는 방법은 `dashboard.js` 맨 위 주석 참조.
    """
    return _DASHBOARD_HTML.read_text(encoding="utf-8")


@router.get("/api/newsletter", dependencies=[Depends(require_admin_basic)])
def admin_api_newsletter(session: Session = Depends(get_session)) -> dict[str, Any]:
    """04 Newsletter 섹션 데이터 (T-027 2단계).

    새 섹션을 만들 때 이 라우트를 본떠 만든다 — 라우트는 HTTP만, 집계는 서비스가 한다.
    """
    return newsletter_section(session)


# --- 회원 관리 모달 (T-027 3a) — 대시보드에서 쓰는 JSON 판 -------------------------
# 기존 폼 엔드포인트(303 리다이렉트)는 서버 렌더 화면용이라 그대로 두고, 여기선 JSON으로 답한다.
# 로직은 양쪽 다 같은 서비스 함수를 부르므로 동작이 갈라지지 않는다.


@router.get("/api/members", dependencies=[Depends(require_admin_basic)])
def admin_api_members(
    q: str | None = Query(default=None),
    program: str | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return members_page(session, q=q, program=program, page=page)


@router.post("/api/members", dependencies=[Depends(require_admin_basic)])
def admin_api_member_create(
    payload: MemberCreate, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        member = create_member(session, payload)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("admin member added (dashboard)")  # PII는 로그에 남기지 않는다
    return {"id": member.id}


@router.post("/api/members/{member_id}/subscribed", dependencies=[Depends(require_admin_basic)])
def admin_api_member_subscribed(
    member_id: int, subscribed: bool = Body(embed=True), session: Session = Depends(get_session)
) -> dict[str, Any]:
    member = _member_or_404(session, member_id)
    changed = set_subscribed(session, member, subscribed=subscribed)
    if changed:
        logger.info(f"admin subscription changed: id={member_id} subscribed={subscribed}")
    return {"changed": changed, "subscribed": member.subscribed}


@router.post("/api/members/{member_id}/program", dependencies=[Depends(require_admin_basic)])
def admin_api_member_program(
    member_id: int,
    program: str = Body(embed=True),
    joined: bool = Body(embed=True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """발송 대상에 넣거나 뺀다 — 지금까지 관리자 화면에 없던 기능."""
    member = _member_or_404(session, member_id)
    changed = set_program(session, member, program, joined=joined)
    if changed:
        logger.info(f"admin program changed: id={member_id} program={program} joined={joined}")
    return {"changed": changed}


@router.delete("/api/members/{member_id}", dependencies=[Depends(require_admin_basic)])
def admin_api_member_delete(
    member_id: int, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        delete_member(session, member_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info(f"admin member deleted (dashboard): id={member_id}")
    return {"deleted": member_id}


# --- 발송 검토 모달 (T-027 3b) --------------------------------------------------
# 여기만 유일하게 **실제 메일이 나가는** 조작이다. 가드는 서버에만 둔다.


@router.get("/api/review", dependencies=[Depends(require_admin_basic)])
def admin_api_review(session: Session = Depends(get_session)) -> dict[str, Any]:
    return review_panel(session)


@router.post("/api/review/settings", dependencies=[Depends(require_admin_basic)])
def admin_api_review_settings(
    payload: SendSettings, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """저장 단계에서 검증한다 — 조립 시점에 터지면 크론이 조용히 실패하고 그날 발송이 빠진다."""
    try:
        save_send_settings(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return review_panel(session)


@router.post("/api/review/build", dependencies=[Depends(require_admin_basic)])
def admin_api_review_build(session: Session = Depends(get_session)) -> dict[str, Any]:
    """오늘 편 조립(멱등) — 같은 날 다시 눌러도 새 편이 생기지 않는다."""
    try:
        build_pilot_daily(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return review_panel(session)


@router.post("/api/review/send", dependencies=[Depends(require_admin_basic)])
def admin_api_review_send(
    background: BackgroundTasks, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """실제 발송. 화면이 뭘 보냈든 **여기서 다시 판정한다** — 화면의 판단을 믿지 않는다.

    (`review_panel`이 같은 조건으로 can_send를 계산하지만, 화면을 열어둔 사이에 수신자가
    바뀔 수 있다. 마지막 판정은 누르는 시점의 서버가 한다.)
    """
    panel = review_panel(session)
    if not panel["can_send"]:
        raise HTTPException(status_code=400, detail=panel["blocked_reason"])

    nl = _todays_pilot_newsletter(session)
    assert nl is not None and nl.id is not None  # can_send 가 이미 보장한다
    background.add_task(send_reviewed, nl.id)
    logger.info(f"admin manual send accepted (dashboard): id={nl.id} n={panel['recipients']}")
    return {"accepted": True, "recipients": panel["recipients"], "newsletter_id": nl.id}


def _member_or_404(session: Session, member_id: int) -> Member:
    try:
        return get_member(session, member_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.post("/members/{member_id}/subscribed", dependencies=[Depends(require_admin_basic)])
def admin_members_set_subscribed(
    member_id: int,
    subscribed: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """구독 상태 되돌리기 (T-025) — 수신거부한 회원이 다시 받고 싶다고 연락해왔을 때의 경로.

    지금까지는 DB를 직접 쓰는 것 말고 방법이 없었다. 되살리기는 **본인 요청이 전제**라
    일괄 처리 API가 아니라 회원 한 명씩 누르는 버튼으로만 존재한다.
    """
    want = subscribed == "1"
    try:
        member = get_member(session, member_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if set_subscribed(session, member, subscribed=want):
        logger.info(f"admin subscription changed: id={member_id} subscribed={want}")
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


# ------------------------------------------------------------------ 탭 4: 참여도 (T-019)


@router.get("/scores", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_scores(session: Session = Depends(get_session)) -> str:
    return render_scores_page(collect_scores(session))


@router.get("/scores.csv", dependencies=[Depends(require_admin_basic)])
def admin_scores_csv(
    tier: list[str] = Query(default=[]),
    session: Session = Depends(get_session),
) -> Response:
    """참여도 명단 CSV 내려받기 (T-023) — `?tier=active&tier=warm`으로 등급 선별.

    행사·베네핏 대상을 고르는 실제 경로다. **PII를 담으므로 Basic 인증 뒤에만 존재한다.**
    """
    # 등급 값을 검증한다. 검증 없이 파일명에 넣었더니 한글 등급(`?tier=활발`)에서
    # Content-Disposition 헤더가 latin-1 인코딩에 실패해 500이 났다 — 화면에 한글 라벨이
    # 보이므로 관리자가 충분히 칠 수 있는 값이다. 모르는 값은 조용히 버린다.
    wanted = [t for t in tier if t in TIER_ORDER]
    if tier and not wanted:
        raise HTTPException(
            status_code=400, detail=f"알 수 없는 등급 — 가능한 값: {', '.join(TIER_ORDER)}"
        )
    body = scores_csv(session, tiers=wanted or None)
    name = f"foodie-scores-{'-'.join(sorted(wanted)) if wanted else 'all'}.csv"
    logger.info(f"scores csv exported: tiers={sorted(wanted) or 'all'}")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ------------------------------------------------------------------ 탭 5: 발송 검토


@router.get("/review", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_review(session: Session = Depends(get_session)) -> str:
    return render_review_page(collect_review(session))


@router.post("/review/settings", dependencies=[Depends(require_admin_basic)])
def admin_review_settings(
    n_headlines: int = Form(),
    n_mains: int = Form(),
    n_domestic: int = Form(),
    n_overseas: int = Form(),
    days: int = Form(),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """발송 조립 설정 저장 (T-014). 검증은 서비스가 하고 실패 사유를 그대로 보여준다.

    이미 조립된 오늘 편에는 소급되지 않는다 — 다시 조립해야 반영된다(화면에 안내).
    """
    try:
        save_send_settings(
            session,
            SendSettings(
                n_headlines=n_headlines,
                n_mains=n_mains,
                n_domestic=n_domestic,
                n_overseas=n_overseas,
                days=days,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/admin/review", status_code=303)


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
