import time
from collections.abc import Callable

import httpx

from app.lib.logger import get_logger

logger = get_logger("http")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 15.0,
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] | None = None,
) -> httpx.Response:
    """GET 요청 + 일시 오류(429/5xx/타임아웃) 지수 백오프 재시도.

    최종 실패 시 httpx.HTTPStatusError 또는 httpx.TransportError를 그대로 올린다 —
    호출부가 "실패"와 "0건"을 구분할 수 있어야 폴백 판단이 가능하다 (T-001 AC1).
    """
    owns_client = client is None
    client = client or httpx.Client(follow_redirects=True)
    try:
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                resp = client.get(url, params=params, headers=headers, timeout=timeout)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in RETRYABLE_STATUS:
                    raise
                last_exc = exc
            except httpx.TransportError as exc:
                last_exc = exc
            if attempt < max_attempts - 1:
                delay = backoff_base * (2**attempt)
                logger.warning(
                    f"retryable failure ({type(last_exc).__name__}), "
                    f"attempt {attempt + 1}/{max_attempts}, retrying in {delay:.1f}s"
                )
                (sleep or time.sleep)(delay)
        assert last_exc is not None
        raise last_exc
    finally:
        if owns_client:
            client.close()
