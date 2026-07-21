"""관리자 현황판 (T-010) — 읽기 전용, HTTP Basic 잠금.

매직링크 로그인 전 임시 인증: 비밀번호 = ADMIN_TOKEN (사용자명은 admin 고정).
브라우저 기본 암호창으로 접근 가능해야 해서 Bearer 헤더 대신 Basic을 쓴다.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.services.admin_status import collect_stats, render_status

router = APIRouter(prefix="/admin", tags=["admin"])
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


@router.get("/status", response_class=HTMLResponse, dependencies=[Depends(require_admin_basic)])
def admin_status(session: Session = Depends(get_session)) -> str:
    return render_status(collect_stats(session))
