#!/usr/bin/env bash
# DB 타겟 안전 스위치 — .env 파일은 건드리지 않고 서브셸 환경변수로만 스왑한다.
# 운영(Supabase)을 타겟할 때는 호스트를 보여주고 명시적 확인을 요구한다.
#
# 사용법:
#   scripts/db_target.sh local    uv run alembic current
#   scripts/db_target.sh supabase uv run alembic upgrade head
set -euo pipefail

usage() {
  echo "사용법: $0 [local|supabase] <명령...>" >&2
  exit 1
}
[ $# -ge 2 ] || usage
target="$1"
shift

env_file="$(cd "$(dirname "$0")/.." && pwd)/.env"
[ -f "$env_file" ] || { echo ".env 없음: $env_file" >&2; exit 1; }

get_var() { grep "^$1=" "$env_file" | head -1 | cut -d= -f2-; }

case "$target" in
  local)
    url="$(get_var DATABASE_URL)"
    ;;
  supabase)
    url="$(get_var SUPABASE_URL)"
    [ -n "$url" ] || { echo ".env에 SUPABASE_URL 없음" >&2; exit 1; }
    # 앱이 요구하는 psycopg 드라이버 접두사 보정
    url="${url/#postgresql:\/\//postgresql+psycopg://}"
    host="$(printf '%s' "$url" | sed -E 's|^[^@]*@([^:/?]+).*|\1|')"
    echo "⚠️  운영 DB(Supabase)를 대상으로 실행합니다: $host" >&2
    printf "계속하려면 'supabase'를 입력하세요: " >&2
    read -r answer
    [ "$answer" = "supabase" ] || { echo "취소됨." >&2; exit 1; }
    ;;
  *) usage ;;
esac

[ -n "$url" ] || { echo "$target 의 접속 문자열을 읽지 못함" >&2; exit 1; }
DATABASE_URL="$url" exec "$@"
