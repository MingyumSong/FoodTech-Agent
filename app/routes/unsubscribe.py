"""수신거부 (T-008).

- GET: 이메일 푸터 링크 클릭 → 확인 페이지.
- POST: RFC 8058 one-click (Gmail 등이 List-Unsubscribe-Post 헤더로 자동 호출).
- 멱등: 이미 거부된 토큰도 성공으로 응답. 존재하지 않는 토큰만 404.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.lib.logger import get_logger
from app.models.member import Member

router = APIRouter(tags=["unsubscribe"])
logger = get_logger("unsubscribe")

_DONE_HTML = """<!DOCTYPE html>
<html lang="ko"><body style="font-family:sans-serif;max-width:480px;margin:80px auto;
text-align:center;color:#1E242B;">
<h2>수신거부가 완료되었습니다</h2>
<p style="color:#55606B;">푸디픽 뉴스레터가 더 이상 발송되지 않습니다.<br>
다시 받고 싶으시면 푸드테크센터로 연락해주세요.</p>
</body></html>"""


def _unsubscribe(token: str, session: Session) -> None:
    member = session.exec(select(Member).where(Member.unsubscribe_token == token)).first()
    if member is None:
        raise HTTPException(status_code=404, detail="invalid token")
    if member.subscribed:
        member.subscribed = False
        session.add(member)
        session.commit()
        logger.info(f"unsubscribed member_id={member.id}")  # PII(이메일) 로그 금지 (C6)


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_get(token: str, session: Session = Depends(get_session)) -> str:
    _unsubscribe(token, session)
    return _DONE_HTML


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_post(token: str, session: Session = Depends(get_session)) -> str:
    _unsubscribe(token, session)
    return _DONE_HTML
