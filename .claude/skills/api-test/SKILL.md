---
name: api-test
description: 로컬 서버 기동 + curl로 엔드포인트 실동작 검증. "/api-test", "API 확인", "엔드포인트 테스트" 요청 시 사용.
---

# /api-test — API 실동작 검증

pytest가 아닌 **실제 서버**로 엔드포인트를 확인한다 (티켓 Verification 절차용).

## 절차

1. DB 준비: `docker compose up -d postgres && uv run alembic upgrade head`
2. 서버 백그라운드 기동:
   ```bash
   uv run uvicorn app.main:app --port 8000
   ```
3. 기본 체크:
   ```bash
   curl -s localhost:8000/health          # {"status":"ok","db":"ok"}
   curl -s localhost:8000/api/members | head -c 300
   ```
4. 잡 엔드포인트는 토큰 포함:
   ```bash
   curl -s -X POST localhost:8000/jobs/ping -H "Authorization: Bearer $JOBS_TOKEN"
   ```
5. 검증 대상 티켓의 Verification 절차를 curl로 재현하고, 끝나면 서버 프로세스를 종료한다.

## 팁

- OpenAPI 문서: http://localhost:8000/docs (엔드포인트 스키마 확인)
