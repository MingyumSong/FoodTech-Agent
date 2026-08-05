#!/usr/bin/env bash
# 로컬 검증 일괄 실행 — CI(.github/workflows/ci.yml)와 동일 단계.
# CI 단계를 바꾸면 여기도 함께 갱신할 것.
#
# 출력은 로그로 받고 **실패할 때만** 꼬리를 찍는다 — 성공 시 한 줄이라 호출부가 ` | tail`을 붙일
# 이유가 없어진다. 파이프를 붙이면 종료코드가 tail 것으로 덮여 실패가 성공으로 보인다(실제 사고 2회).
set -euo pipefail
cd "$(dirname "$0")/.."

log="$(mktemp -t foodtech-check)"
trap 'rm -f "$log"' EXIT

run() {
  echo "── $* ──" >>"$log"
  if ! "$@" >>"$log" 2>&1; then
    echo "❌ 실패: $*" >&2
    tail -40 "$log" >&2
    echo "전체 로그: $log" >&2  # 실패 시엔 trap을 풀어 로그를 남긴다
    trap - EXIT
    exit 1
  fi
}

run uv run ruff format --check .  # CI(ci.yml)가 도는 단계 — 빠져 있으면 로컬만 초록불이 된다
run uv run ruff check .
run uv run pyright
run uv run pytest -q

echo "✅ ruff + pyright + pytest 통과 ($(grep -c . "$log")줄 출력 억제됨)"
