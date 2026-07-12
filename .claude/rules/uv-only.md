# C1: 패키지 작업은 uv로만

- 의존성 추가/삭제는 `uv add` / `uv remove`. pip 직접 호출 금지.
- 실행은 `uv run <cmd>` (예: `uv run pytest`, `uv run uvicorn app.main:app`).
- `uv.lock`은 uv 명령으로만 갱신되며 반드시 커밋한다.
- Python 버전은 `.python-version`(3.13) 고정 — 임의 변경 금지.
