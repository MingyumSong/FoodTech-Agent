#!/usr/bin/env bash
# 클론 직후 화면을 띄운다 — 시크릿 없이.
#
#   bash scripts/dev.sh
#   → http://localhost:8000/admin/dashboard
#
# 왜 스크립트인가: 새로 합류하는 사람이 막히는 지점은 코드가 아니라 준비 절차다.
# DB 띄우기 → 스키마 적용 → 서버 실행이 한 줄이어야 첫 화면까지 도달한다.
#
# 시크릿이 없으면 발송·수집·LLM은 동작하지 않는다. 화면 개발엔 필요 없다 —
# 필요해지면 .env.example 을 .env 로 복사하고 값을 채운다.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo "⚠️  .env 가 있습니다. 거기 ADMIN_TOKEN 이 있으면 인증이 켜집니다"
  echo "    (인증 없이 보려면 .env 를 잠시 치우거나 ADMIN_TOKEN 을 비우세요)"
  echo
fi

echo "▶ 1/3  Postgres 기동"
docker compose up -d postgres

echo "▶ 2/3  스키마 적용 (DB가 받을 준비될 때까지 재시도)"
for i in $(seq 1 20); do
  if uv run alembic upgrade head 2>/dev/null; then
    break
  fi
  [ "$i" = 20 ] && { echo "DB에 연결하지 못했습니다 — 'docker compose ps' 로 확인하세요" >&2; exit 1; }
  sleep 1
done

echo "▶ 3/3  서버 실행"
echo
echo "   대시보드:  http://localhost:8000/admin/dashboard"
echo "   API 문서:  http://localhost:8000/docs"
echo
echo "   데이터가 비어 있으면 화면도 비어 보입니다 — 정상입니다."
echo "   샘플 데이터가 필요하면 .claude/skills/seed-data 를 참고하세요."
echo

exec uv run uvicorn app.main:app --reload --port 8000
