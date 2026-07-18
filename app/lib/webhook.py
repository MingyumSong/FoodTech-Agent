import base64
import hashlib
import hmac
import time

# svix 표준 리플레이 방지 허용 오차 (초) — 이보다 오래된/미래의 타임스탬프는 거부
TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_svix_signature(
    secret: str,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    body: bytes,
    *,
    now: float | None = None,
) -> bool:
    """Resend(svix) 웹훅 서명 검증 — 외부 의존성 없이 표준 HMAC-SHA256.

    서명 대상은 "{svix-id}.{svix-timestamp}.{원문 body}" 이므로 body는 파싱 전
    원본 바이트여야 한다. 시크릿은 대시보드가 주는 "whsec_<base64 key>" 형식.
    """
    if not (secret and svix_id and svix_timestamp and svix_signature):
        return False
    try:
        timestamp = int(svix_timestamp)
    except ValueError:
        return False
    current = time.time() if now is None else now
    if abs(current - timestamp) > TIMESTAMP_TOLERANCE_SECONDS:
        return False
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"))
    except ValueError:
        return False
    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()
    # 헤더는 "v1,<sig> v1,<sig2>" 형태 — 키 로테이션 중엔 서명이 여러 개일 수 있다
    for part in svix_signature.split(" "):
        version, _, signature = part.partition(",")
        if version == "v1" and hmac.compare_digest(signature, expected):
            return True
    return False
