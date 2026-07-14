#!/usr/bin/env bash
# 로컬 검증 일괄 실행 — CI(.github/workflows/ci.yml)와 동일 단계.
# CI 단계를 바꾸면 여기도 함께 갱신할 것.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff check .
uv run pyright
uv run pytest -q

echo "✅ ruff + pyright + pytest 통과"
