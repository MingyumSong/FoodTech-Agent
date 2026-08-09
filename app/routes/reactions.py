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


def _message(value: str, previous: str | None) -> tuple[str, str]:
    """(제목, 본문) — 지금 누른 것이 처음인지·같은 것인지·바꾼 것인지 말해준다.

    수신자 피드백: "버튼 하나 누르고 다른 버튼도 누를 수 있게 되어있음".
    기록은 (회원,편)당 1행으로 수렴하고 있었지만 화면이 매번 똑같은 말을 해서
    바뀐 줄을 알 수 없었다. 눌린 결과를 그대로 비춰주는 게 고칠 지점이다.
    """
    now = _LABELS[value]
    if previous is None:
        return "고맙습니다", f"'{now}'로 기록했습니다."
    if previous == value:
        return "이미 기록되어 있어요", f"이 편은 '{now}'로 남아 있습니다."
    return "바꿨습니다", f"'{_LABELS[previous]}' → '{now}'로 바꿨습니다."


def _done_html(value: str, previous: str | None) -> str:
    title, body = _message(value, previous)
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Apple SD Gothic Neo',sans-serif;max-width:480px;margin:80px auto;
text-align:center;color:#16181D;padding:0 20px;">
<h2 style="color:#1F6FB2;">{title}</h2>
<p style="color:#4B5563;line-height:1.7;">{body}<br>
남겨주신 반응이 다음 픽을 고르는 데 쓰입니다.</p>
<p style="color:#9CA3AF;font-size:13px;line-height:1.7;">
마음이 바뀌면 메일에서 다른 버튼을 눌러도 됩니다 — 한 편에 하나만, 마지막 것으로 남습니다.<br>
창을 닫으셔도 됩니다.</p>
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

    previous = record_reaction(session, member=member, newsletter_id=newsletter_id, value=value)
    return _done_html(value, previous)
