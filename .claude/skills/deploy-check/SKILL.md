---
name: deploy-check
description: Railway 배포 후 검증 루틴. "/deploy-check", "배포 확인", "배포 검증", railway up 직후에 사용.
---

# /deploy-check — 배포 후 검증 루틴

`railway up`은 권한 분류기 때문에 사용자가 `!`로 직접 실행한다. 그 직후 이 루틴으로 검증한다.
운영 URL: `https://app-production-945c.up.railway.app` (CLAUDE.md 결정, CNAME 전까지)

## 절차

1. **대기 + 기본 검증** (백그라운드 1회 실행 — 폴링 낭비 금지):
   ```bash
   sleep 150
   curl -s -m 15 "https://app-production-945c.up.railway.app/health"; echo
   railway logs --service app 2>&1 | grep -E "Application startup|Uvicorn running|upgrade" | tail -3
   ```
   기대: `{"status":"ok","db":"ok"}` + `Application startup complete`. 마이그레이션이 포함된
   배포면 `Running upgrade` 줄로 리비전 적용도 확인.
2. **이번 배포에서 추가·변경된 엔드포인트 스모크** — 인증 실패 경로 위주(안전):
   - 새 `/jobs/*` → 토큰 없이 401 확인
   - 새 공개 라우트 → 정상/404 등 기대 코드 확인
   - 예: `curl -s -o /dev/null -w "%{http_code}\n" -m 15 -X POST "$APP/jobs/새엔드포인트"`
3. **기능 라이브 검증**이 필요하면 (스키마 변경·크론 대상 기능): 해당 `/jobs/*`를
   `JOBS_TOKEN`으로 트리거 → Supabase에서 결과 행 확인 (읽기 전용 쿼리).
4. 결과를 티켓 AC나 커밋 메시지에 기록.

## 주의

- `sleep 150`은 빌드+preDeploy(alembic)+헬스체크 시간 — 실패 시 한 번 더 60s 후 재확인,
  그래도 안 되면 `railway logs`에서 빌드 오류를 찾는다 (추측 재배포 금지).
- 시크릿 값은 출력하지 않는다. 시크릿 추가가 동반된 배포면 먼저 `/add-env` 절차 확인.
