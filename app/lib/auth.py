from fastapi import Header, HTTPException

from app.config import settings


def require_admin_token(authorization: str = Header(default="")) -> None:
    """관리자 API 검문 — 매직링크 로그인(관리자 페이지) 도입 전까지의 잠금장치.

    회원 PII를 다루는 라우터는 이 의존성 없이 공개 URL에 노출하면 안 된다.
    """
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN not configured")
    if authorization != f"Bearer {settings.admin_token}":
        raise HTTPException(status_code=401, detail="invalid admin token")
