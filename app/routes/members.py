from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlmodel import Session

from app.db import get_session
from app.lib.auth import require_admin_token
from app.models.member import MemberCreate, MemberRead
from app.services import members as members_service
from app.services.member_import import import_members

# 회원 PII 라우터 — 전 엔드포인트 관리자 토큰 필수 (공개 URL 노출 금지)
router = APIRouter(
    prefix="/api/members",
    tags=["members"],
    dependencies=[Depends(require_admin_token)],
)


@router.get("", response_model=list[MemberRead])
def list_members(
    program: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    return members_service.list_members(session, program=program, limit=limit, offset=offset)


@router.get("/{member_id}", response_model=MemberRead)
def get_member(member_id: int, session: Session = Depends(get_session)):
    return members_service.get_member(session, member_id)


@router.post("", response_model=MemberRead, status_code=201)
def create_member(data: MemberCreate, session: Session = Depends(get_session)):
    return members_service.create_member(session, data)


@router.post("/import")
async def import_members_file(
    file: UploadFile,
    program: str | None = Query(default=None),
    dry_run: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """구글시트 다운로드 파일(CSV/XLSX) 업서트 — dry_run=true로 먼저 미리보기 권장 (T-007)."""
    content = await file.read()
    return import_members(
        session, content, file.filename or "upload.csv", program=program, dry_run=dry_run
    )
