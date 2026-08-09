"""수신거부 (T-008, 확인 단계 T-025).

- GET: 이메일 푸터 링크 클릭 → **확인 페이지만** 띄운다. 아무것도 바꾸지 않는다.
- POST: 확인 페이지의 버튼 + RFC 8058 one-click (Gmail 등이 List-Unsubscribe-Post로 자동 호출).
- 멱등: 이미 거부된 토큰도 성공으로 응답. 존재하지 않는 토큰만 404.

**GET에서 부작용을 뺀 이유**: 메일 클라이언트·보안 게이트웨이가 링크를 미리 열어보면(프리페치)
읽지도 않은 사람이 해지된다. 되돌릴 방법이 없는 손실이라 확인 한 단계를 넣었다.
봇은 GET만 하고 POST는 안 하므로 이 분리가 오탐만 정확히 걸러낸다.
Gmail의 one-click은 POST라 영향받지 않는다 — 목록 관리 UI의 편의는 그대로다.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.lib.logger import get_logger
from app.models.member import Member
from app.services.members import set_subscribed

router = APIRouter(tags=["unsubscribe"])
logger = get_logger("unsubscribe")

_PAGE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Apple SD Gothic Neo',sans-serif;max-width:480px;margin:80px auto;
text-align:center;color:#1E242B;padding:0 20px;">{inner}</body></html>"""

_CONFIRM_INNER = """<h2>수신거부 하시겠어요?</h2>
<p style="color:#55606B;line-height:1.7;">아래 버튼을 누르면 푸디픽 뉴스레터가
더 이상 발송되지 않습니다.</p>
<form method="post" action="/unsubscribe/{token}" style="margin-top:24px;">
<button type="submit" style="padding:12px 26px;background:#B42318;color:#fff;border:0;
border-radius:8px;font-size:15px;cursor:pointer;">수신거부하기</button></form>
<p style="color:#9CA3AF;font-size:13px;margin-top:28px;">
잘못 누르셨다면 이 창을 그냥 닫으시면 됩니다 — 아직 아무것도 바뀌지 않았습니다.</p>"""

_DONE_INNER = """<h2>수신거부가 완료되었습니다</h2>
<p style="color:#55606B;line-height:1.7;">푸디픽 뉴스레터가 더 이상 발송되지 않습니다.<br>
다시 받고 싶으시면 푸드테크센터로 연락해주세요.</p>"""


def _member_by_token(token: str, session: Session) -> Member:
    member = session.exec(select(Member).where(Member.unsubscribe_token == token)).first()
    if member is None:
        raise HTTPException(status_code=404, detail="invalid token")
    return member


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_get(token: str, session: Session = Depends(get_session)) -> str:
    """확인 페이지 — 여기서는 구독 상태를 건드리지 않는다(오클릭·프리페치 방어)."""
    member = _member_by_token(token, session)
    if not member.subscribed:  # 이미 해지된 사람에게 다시 물어볼 것 없다
        return _PAGE.format(inner=_DONE_INNER)
    return _PAGE.format(inner=_CONFIRM_INNER.format(token=token))


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_post(token: str, session: Session = Depends(get_session)) -> str:
    member = _member_by_token(token, session)
    if set_subscribed(session, member, subscribed=False):
        logger.info(f"unsubscribed member_id={member.id}")  # PII(이메일) 로그 금지 (C6)
    return _PAGE.format(inner=_DONE_INNER)
