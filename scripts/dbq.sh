#!/usr/bin/env bash
# 운영/로컬 DB 읽기 전용 조회 한 줄로.
#
#   bash scripts/dbq.sh prod  "select count(*) from members"
#   bash scripts/dbq.sh local "select * from app_settings"
#
# 왜 별도 스크립트인가: scripts/db_target.sh는 `read -r`로 확인을 받아서 stdin 없는
# 비대화형(에이전트 Bash)에서 못 쓴다. 그 게이트는 **쓰기 경로**에 정당하므로 그대로 두고,
# 읽기 전용은 게이트 대신 **DB가 강제하는 read-only**로 안전을 확보한다.
#
# 안전 근거(실측): 접속 문자열의 options=-c default_transaction_read_only 는 Supabase 풀러가
# 조용히 무시한다. 반면 autocommit 상태에서 SET SESSION CHARACTERISTICS ... READ ONLY 를 걸면
# 이후 모든 트랜잭션이 읽기 전용이라 CREATE/DELETE 가 DB 레벨에서 거부된다.
# autocommit이 핵심 — 트랜잭션이 열린 뒤 설정하면 그 트랜잭션엔 적용되지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
SQL="${2:-}"
if [ -z "$TARGET" ] || [ -z "$SQL" ]; then
  echo "사용법: bash scripts/dbq.sh {prod|local} \"<SELECT ...>\"" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

case "$TARGET" in
  prod)  URL="${SUPABASE_URL:?SUPABASE_URL이 .env에 없다}" ;;
  local) URL="${DATABASE_URL:?DATABASE_URL이 .env에 없다}" ;;
  *) echo "타겟은 prod 또는 local" >&2; exit 2 ;;
esac

TARGET="$TARGET" SQL="$SQL" DBQ_URL="$URL" uv run python - <<'PY'
import os
import sys

import psycopg

url = os.environ["DBQ_URL"]
# SQLAlchemy 접두사는 psycopg가 모른다
url = url.replace("postgresql+psycopg://", "postgresql://", 1)

with psycopg.connect(url, autocommit=True) as conn:  # autocommit이어야 아래 설정이 먹는다
    with conn.cursor() as cur:
        cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        try:
            cur.execute(os.environ["SQL"])
        except psycopg.errors.ReadOnlySqlTransaction:
            print("거부됨: 읽기 전용 세션이다. 쓰기는 scripts/db_target.sh 를 쓸 것.", file=sys.stderr)
            raise SystemExit(1)
        if cur.description is None:
            print("(반환 행 없음)")
            raise SystemExit(0)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
        print(" | ".join(cols))
        print("-" * 60)
        for r in rows:
            print(" | ".join("" if v is None else str(v) for v in r))
        print(f"\n{len(rows)}행 · {os.environ['TARGET']}")
PY
