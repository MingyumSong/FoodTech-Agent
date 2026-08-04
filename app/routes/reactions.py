"""디저트 코너 원클릭 반응 수집 (T-013).

이메일에서 바로 눌리는 링크라 인증이 없다. 대신 회원 식별에 추측 불가능한 토큰을 쓴다 —
`member.unsubscribe_token`(secrets.token_urlsafe(16))을 재사용한다. 같은 메일 안에 이미
들어 있는 토큰이라 노출 범위가 늘지 않고, 열거로 남의 반응을 조작할 수 없다.

메일 클라이언트의 프리페치(봇 클릭)가 GET을 대신 눌러버릴 수 있지만, 반응은 마지막 값으로
수렴하는 멱등 기록이라 중복 적재로 통계가 부풀지 않는다.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.lib.logger import get_logger
from app.models.member import Member
from app.services.engagement import REACTION_VALUES, record_reaction

router = APIRouter(tags=["reactions"])
logger = get_logger("reactions")

_LABELS = {"good": "좋았어요", "ok": "보통이에요", "bad": "별로였어요"}


def _done_html(label: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Apple SD Gothic Neo',sans-serif;max-width:480px;margin:80px auto;
text-align:center;color:#16181D;padding:0 20px;">
<h2 style="color:#1F6FB2;">고맙습니다</h2>
<p style="color:#4B5563;line-height:1.7;">'{label}'로 기록했습니다.<br>
남겨주신 반응이 다음 픽을 고르는 데 쓰입니다.</p>
<p style="color:#9CA3AF;font-size:13px;">창을 닫으셔도 됩니다.</p>
</body></html>"""


@router.get("/reactions/{token}/{newsletter_id}/{value}", response_class=HTMLResponse)
def react(
    token: str,
    newsletter_id: int,
    value: str,
    session: Session = Depends(get_session),
) -> str:
    if value not in REACTION_VALUES:
        raise HTTPException(status_code=404, detail="unknown reaction")
    member = session.exec(select(Member).where(Member.unsubscribe_token == token)).first()
    if member is None:
        raise HTTPException(status_code=404, detail="invalid token")

    record_reaction(session, member=member, newsletter_id=newsletter_id, value=value)
    return _done_html(_LABELS[value])
