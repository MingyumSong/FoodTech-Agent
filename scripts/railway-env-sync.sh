#!/usr/bin/env bash
# .env의 시크릿을 Railway 서비스(app) 환경변수로 동기화한다.
# 값이 셸 밖으로 출력되지 않도록 여기서 직접 소싱한다. (T-005 B단계)
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

railway variables --service app --skip-deploys \
  --set "DATABASE_URL=$SUPABASE_URL" \
  --set "JOBS_TOKEN=$JOBS_TOKEN" \
  --set "ADMIN_TOKEN=$ADMIN_TOKEN" \
  --set "APP_ENV=prod" \
  --set "RESEND_API_KEY=$RESEND_API_KEY" \
  --set "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" \
  --set "NAVER_CLIENT_ID=$NAVER_CLIENT_ID" \
  --set "NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET" \
  --set "BRAVE_SEARCH_API_KEY=$BRAVE_SEARCH_API_KEY" \
  --set "RESEND_WEBHOOK_SECRET=$RESEND_WEBHOOK_SECRET" \
  > /dev/null

echo "✅ Railway(app) 환경변수 10개 설정 완료 (값은 출력하지 않음)"
railway variables --service app --kv | cut -d= -f1
