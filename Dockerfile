FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

EXPOSE 8000
# Railway가 PORT를 주입하므로 sh -c로 변수 확장 (로컬 기본값 8000), exec로 SIGTERM 직접 수신
CMD ["/bin/sh", "-c", "exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
