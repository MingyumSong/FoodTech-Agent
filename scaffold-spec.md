# Scaffold Spec: FoodTech Hub

Created: 2026-07-12
Goal: 회원 관리 + 뉴스레터 + 참여 추적 시스템을 위한 신규 코드베이스 기반(foundation) 세팅

## L0: Goal

**Confirmed Goal**: 백엔드 기반을 새로 세팅한다 — 프로젝트 구조, 수직 슬라이스 예시(라우트→로직→DB→테스트), 테스트 인프라, 가드레일(CLAUDE.md·룰·린트), 하네스(스킬·훅) 포함. 에이전트가 이 골격만 읽고 T-001 같은 티켓을 일관된 패턴으로 구현할 수 있는 상태가 완료 기준.

**Non-Goals**:
- 기능 구현 (뉴스 수집, Resend 웹훅 추적, Activity Score — 티켓으로 진행)
- 운영 배포
- `archive/foodtech-hub-deploy/` 수정 (참고 전용)

## L1: Environment

- **Directory**: `/Users/songmingyum/Desktop/FoodTech-Agent` — 신규 코드 없음 (docs/, archive/, CLAUDE.md만 존재). 그린필드 확정.
- **Python**: 3.14.0 (python.org 프레임워크 설치), pip3 있음. **uv/poetry 없음.**
- **Node**: v25.2.1, npm 있음 (pnpm 없음) — 백엔드가 Python이면 참고용
- **Docker**: 29.4.0 + Compose v5.1.1 설치됨
- **Git**: main 브랜치, origin 대비 ahead 6, 워킹트리에 문서 변경 있음
- **Platform**: macOS 15.6, ARM64 (Apple Silicon)

## L2: Architecture Decisions

### Decisions

| ID | Decision | Rationale | Assumed? |
|----|----------|-----------|----------|
| D1 | FastAPI + SQLModel + Alembic | 프로토타입과 같은 조합이라 로직 이식 용이. 스키마가 계속 진화(이벤트·Score)하므로 마이그레이션 필수 | No |
| D2 | DB: 운영 Supabase Postgres, 로컬·테스트는 Docker Postgres | 운영-로컬 엔진 통일로 SQLite 분기 버그 원천 차단 | No |
| D3 | 의존성: uv + uv.lock, Python 3.13 고정 | 재현 가능한 환경. 3.14는 생태계 호환 리스크로 회피 | 3.13 pin: Yes |
| D4 | 배포: Docker화까지만, 플랫폼은 미정 | 기관 org 이관 예정이라 플랫폼 중립 유지 | No |
| D5 | 스케줄링: GitHub Actions cron → 인증된 `/jobs/*` HTTP 엔드포인트 | 앱 무상태 유지, 실행 로그·수동 재실행 GitHub에서, 레포 이관 시 함께 이동 | No |
| D6 | 테스트: pytest + 실제 Postgres. CI: GitHub Actions (ruff + 타입체크 + pytest) | 발송 사고 방지 안전망. 티켓 Verification의 기계적 부분을 CI가 대행 | No |
| D7 | 프론트: FastAPI가 서빙하는 정적 HTML (공개 + admin) | CLAUDE.md 기존 결정. 대시보드는 별도 BI | No (기존 결정) |
| D8 | API: REST JSON + Pydantic(SQLModel) 스키마 | FastAPI 기본. OpenAPI 문서 자동 생성 | No |
| D9 | 외부 연동: Resend(메일), OpenRouter(LLM), 네이버 API·RSS·CrossRef(뉴스) | CLAUDE.md 기존 결정 | No (기존 결정) |
| D10 | 타입체크: pyright | SQLModel(Pydantic 기반)과 궁합, 빠름 | Yes |

### Constraints

- C1: 패키지 작업은 uv로만 (`uv add`/`uv run`). pip 직접 호출 금지. `uv.lock` 커밋.
- C2: 스키마 변경은 반드시 Alembic 마이그레이션으로. 운영에서 `create_all` 금지.
- C3: Supabase 특화 기능(RLS, Auth, Storage, pg_cron) 사용 금지 — 순수 Postgres 기능만 (기관 이관 중립성).
- C4: `/jobs/*` 엔드포인트는 토큰 인증 + 멱등(중복 호출 안전) + 즉시 응답(장시간 작업은 백그라운드 처리).
- C5: `archive/` 수정 금지 (참고 전용).
- C6: 시크릿 하드코딩 금지. `.env` 로컬 / 배포 플랫폼 주입. `.env.example` 유지.

### Activated Extensions

- [x] Data Layer (Postgres + Alembic 마이그레이션 + seed 데이터)
- [x] Docker/Infra (compose: postgres + api, Dockerfile)
- [x] Runtime Patterns (health check, graceful shutdown — 발송·크론 전제)
- [ ] Type Contracts (프론트가 정적 HTML이라 코드젠 불요 — FastAPI 자동 OpenAPI로 충분)

### Known Gaps (Inversion Probe 결과)

- 3,000명 발송의 실행 모델(배치 크기, Resend 배치 API, 타임아웃)은 발송 티켓에서 상세화 — C4가 구조적 완충.
- 전면 재구조 시나리오: "외부에서 접근 불가한 폐쇄망 배포" 요구 시 D5(외부 크론) 붕괴 — 현 로드맵상 가능성 낮음, 잡 로직을 엔드포인트와 분리된 함수로 두면(서비스 레이어) 트리거만 교체 가능.
- GitHub Actions 무료 한도: private 레포 월 2,000분 — 일 1회 수집 + 주 1회 발송이면 여유. 초과 조짐 시 pg_cron 재검토.
- Python 3.13 + SQLModel/Alembic 호환은 T1(프로젝트 초기화)에서 실검증.

## L3: Harness Setup

### Domain Context

CLAUDE.md 기존 내용 유지 + 스캐폴딩 시 용어 정의 보강:
- **회원(member)**: 4개 프로그램(최고책임자과정·계약학과·사업화교육·협의회)에 걸친 약 3,000명. `program` 세그먼트로 관리.
- **이벤트(engagement event)**: 회원×뉴스레터×뉴스 단위의 open/click/bounce 기록 (Resend 웹훅 1차 수단).
- **Activity Score**: 행동별 가중합 (열람<클릭<전달). 정밀 지표가 아닌 상대 순위 도구.
- **Active/Dormant**: Score 기반 자동 분류. 행사·베네핏 선별 근거.

### Team Conventions

- 커밋: Conventional Commits prefix(feat/fix/docs/chore) + 한국어 요약. main 직커밋.
- 티켓 작업 커밋에는 티켓 ID 포함 (예: `feat: T-001 뉴스 수집 폴백`).
- 솔로 프로젝트. 단, 기관 org 이관 예정 → 기록 가독성 우선.

### Rules (from Constraints)

| Constraint | Rule File | Status |
|-----------|-----------|--------|
| C1: uv 전용 | `.claude/rules/uv-only.md` | Approved |
| C2: Alembic 필수 | `.claude/rules/alembic-migrations.md` | Approved |
| C3: Supabase 특화 금지 | `.claude/rules/plain-postgres.md` | Approved |
| C4: 잡 엔드포인트 규약 | `.claude/rules/job-endpoints.md` | Approved |
| C5: archive 수정 금지 | `.claude/rules/archive-readonly.md` | Approved |
| C6: 시크릿 관리 | `.claude/rules/secrets.md` | Approved |

### Skills

| Skill | Description | Source |
|-------|-------------|--------|
| `/migrate` | Alembic 리비전 생성 + 적용 + 모델-스키마 일치 확인 | D1 |
| `/seed-data` | 개발용 가짜 회원·뉴스레터·이벤트 시드 | D2 |
| `/api-test` | 로컬 서버 기동 + 핵심 엔드포인트 curl 검증 | D8 |

### Hooks

| Hook | Type | Trigger |
|------|------|---------|
| `ruff format` | PostToolUse | .py 파일 Edit/Write 후 자동 포맷 |
| `.env*` 수정 차단 | PreToolUse | 시크릿 파일 보호 |
| `uv.lock` 수정 차단 | PreToolUse | lockfile은 uv 명령으로만 갱신 |

## L4: Plan

### Requirements

| ID | Requirement | Source | Conditional? |
|----|------------|--------|-------------|
| R1 | Code Structure — 디렉터리 구조 + 수직 슬라이스 예시(members 리소스: route→service→model→migration→test) + importable 유틸(config/logger/errors) | L2 | No |
| R2 | Test Infrastructure — pytest + Docker Postgres 픽스처, 소스 구조를 미러링하는 테스트 구조 | L2 | No |
| R3 | Guard Rails — CLAUDE.md 갱신(아키텍처 규칙·도메인·컨벤션·스킬·훅 요약), ruff+pyright, CI(lint+typecheck+test), .env.example | L2 | No |
| R5 | Data Layer — Postgres 연결 모듈, Alembic 마이그레이션 체계, seed 스크립트 | L2 | Activated |
| R6 | Docker/Infra — compose(postgres+api), api Dockerfile | L2 | Activated |
| R7 | Runtime Patterns — /health, graceful shutdown, /jobs/* 스켈레톤(토큰 인증+멱등 패턴 예시) | L2 | Activated |
| R8 | Project Rules — C1~C6 → .claude/rules/ 6개 파일 | L3 | Approved |
| R9 | Domain Skills — /migrate, /seed-data, /api-test | L3 | Approved |
| R10 | Project Hooks — ruff 자동포맷, .env·uv.lock 수정 차단 | L3 | Approved |

### Task DAG

| ID | Task | Fulfills | Depends On | Status |
|----|------|----------|------------|--------|
| T1 | 프로젝트 초기화 — uv init, Python 3.13 pin, pyproject(FastAPI·SQLModel·Alembic·pytest·ruff·pyright), 디렉터리 골격 | R1 | - | done |
| T2 | Guard Rails — CLAUDE.md 갱신, ruff/pyright 설정, GitHub Actions CI, .env.example, .claude/rules/ 6개 | R3, R8 | T1 | done |
| T4 | 테스트 인프라 — pytest 설정, Postgres 테스트 픽스처(트랜잭션 롤백), tests/ 구조 | R2 | T1 | done |
| T6 | Data Layer — compose postgres, engine/session 모듈, Alembic 초기화, seed 스크립트 골격 | R5 | T1 | done |
| T3 | **수직 슬라이스 예시 — members 리소스** (model→migration→service→route→test 전체 관통 + lib/config·logger·errors 유틸) | R1 | T2, T4, T6 | done |
| T7 | Docker/Infra — api Dockerfile, compose 통합 (api+postgres 한 번에 기동) | R6 | T1 | done |
| T8 | Runtime Patterns — /health, graceful shutdown, /jobs/ping 스켈레톤(토큰 인증+멱등 예시) | R7 | T3 | done |
| T_SKILL | 스킬 생성 — .claude/skills/{migrate,seed-data,api-test} | R9 | T3 | done |
| T_HOOK | 훅 설정 — .claude/settings.json | R10 | T1 | done |
| TF | 스캐폴드 검증 — lint/typecheck/test 전체 통과, compose 기동, 에이전트 확장성 체크(T-001을 이 골격 위에서 구현 가능한가) | - | all | done |

### Quality Criteria

- Agent extensibility: members 수직 슬라이스가 참조 구현 (T3)
- Testability: 실제 Postgres 픽스처 + exemplar 테스트 (T4)
- Drift resistance: CLAUDE.md + rules 6개 + ruff/pyright + CI (T2)
- Cross-session continuity: CLAUDE.md 도메인·컨벤션 + docs/tickets/ 워크플로 (T2)
- Task automation: 스킬 3개 (T_SKILL), 훅 3개 (T_HOOK)
