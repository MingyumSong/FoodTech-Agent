# T-005: Railway 배포 (선행 준비 + 배포 본체)

Status: DOING (2026-07-18 — **A 선행 준비 완료(AC1~6)**. Railway 계정 인증 완료 후 B 배포 본체 진행)

## Problem

앱이 로컬에서만 동작한다. T-003(Resend 웹훅 수신)은 공개 URL이 필수이고, 24h 뉴스 수집
크론도 공개 엔드포인트를 호출해야 하므로 배포가 선행 조건이다. 배포 PaaS는 Railway로
확정(결정 12: 월 $5 Hobby, 슬립 없음). 희정 계정 생성 완료, **인증 대기 중** — 인증 전에
로컬에서 끝낼 수 있는 준비를 모두 마친다.

## Context

- Dockerfile은 스캐폴딩 때 작성됨(a93020c) — 단, Railway 미대응 지점 3개:
  ① CMD가 8000 하드코딩(Railway는 `PORT` 환경변수 주입, exec-form이라 변수 확장 안 됨)
  ② 배포 시 `alembic upgrade head` 자동 실행 없음
  ③ `.dockerignore` 부재(빌드 컨텍스트에 archive/·data/·.venv 포함됨)
- 레포가 PUBLIC — 회원 PII 임포트 전 private 전환 필수(보안 P0).
- `JOBS_TOKEN`이 개발용 값 — 운영 전 교체 필요.
- `data/news_cache.json`은 컨테이너 로컬 파일 = Railway 재배포 시 소실. 24h 수집 크론이
  재생성하므로 파일럿에선 허용(영속화는 추후 DB 이관 검토 — 별도 티켓).

## Scope

**A. 선행 준비 (인증 전, 이번 단계)**
- `docs/tickets/T-005_railway-deploy.md` (이 파일)
- GitHub 레포 private 전환 (gh CLI — 코드 변경 아님)
- `Dockerfile` — PORT 환경변수 대응 (shell-form CMD, 기본값 8000 유지)
- `.dockerignore` 신설
- `railway.json` 신설 — healthcheckPath=/health, preDeployCommand=alembic upgrade head
- JOBS_TOKEN 신규 생성 (`.env` 반영은 사용자가 수동 — 훅이 .env 편집 차단)

**B. 배포 본체 (인증 후)**
- Railway 프로젝트 생성(GitHub 연동) + 환경변수 세팅
  (DATABASE_URL=Supabase, JOBS_TOKEN, RESEND_API_KEY, NAVER_*, BRAVE_*, OPENROUTER_API_KEY, APP_ENV=prod)
- `admin.foodtech-center.org` CNAME 연결(Cloudflare)
- 24h 뉴스 수집 크론 워크플로(`news-refresh.yml`) — 배포 URL 필요해서 이 단계
- Scope 밖: T-003 웹훅 구현, Activity Score, 발송 크론

## Acceptance Criteria

**A. 선행 준비**
- [x] AC1: 레포 visibility가 PRIVATE (gh repo view로 확인) ✅ 2026-07-18
- [x] AC2: `docker build` 성공 + 컨테이너가 `PORT` 환경변수(예: 7777)로 기동돼 `/health` 200 응답
      ✅ `{"status":"ok","db":"ok"}` + SIGTERM 0.4s 종료(exec 패턴) + 이미지 내 alembic 실행 확인
- [x] AC3: `.dockerignore`로 archive/·data/·.venv·.env·docs/·tests/가 빌드 컨텍스트에서 제외됨
      ✅ 이미지 내 파일 목록 = app/·migrations/·scripts/·alembic.ini·pyproject.toml·uv.lock만
- [x] AC4: `railway.json`에 healthcheckPath(/health)와 preDeployCommand(alembic upgrade head) 정의
- [x] AC5: 신규 JOBS_TOKEN 생성·전달 (openssl rand -hex 32) ✅ 사용자 `.env` 반영 + Railway 환경변수 예정
- [x] AC6: `bash scripts/check.sh` 통과 (기존 테스트 회귀 없음) ✅ 32 passed

**B. 배포 본체 (인증 후)**
- [ ] AC7: 배포 URL에서 `/health` 200 (Supabase 연결 확인)
- [ ] AC8: preDeploy로 Supabase 스키마가 head 리비전과 일치
- [ ] AC9: `POST /jobs/news-refresh` (신규 JOBS_TOKEN) → `/health/news` ok
- [ ] AC10: admin.foodtech-center.org에서 앱 응답 (Cloudflare CNAME + Railway 커스텀 도메인)
- [ ] AC11: news-refresh.yml 크론이 배포 URL 호출 성공

## Verification

**A (인증 전):**
```bash
gh repo view --json visibility          # PRIVATE
docker build -t foodtech-app .
docker run --rm -e PORT=7777 -e DATABASE_URL=postgresql+psycopg://foodtech:foodtech@host.docker.internal:5432/foodtech -p 7777:7777 foodtech-app
curl -s http://localhost:7777/health    # {"status":"ok","db":"ok"}
bash scripts/check.sh
```

**B (인증 후):** 배포 URL에 대해 AC7~AC11을 curl로 순서대로 확인.

## Notes

- private 전환 후 GitHub Actions는 무료 2,000분/월 한도 적용 — 현재 CI 사용량이면 여유.
- preDeployCommand는 배포 이미지·환경변수로 별도 컨테이너에서 실행됨(Railway 표준 패턴) —
  C4 규약(잡 로직 서비스 분리)과 무관한 배포 인프라 단계라 예외 아님.
