# T-002 발송·추적 코어 스키마 (members 확장 + member_programs + newsletters + send_logs + engagement_events)

Type: FEAT
Status: DONE (2026-07-12 — AC 4/4 충족, Verification 통과: upgrade/downgrade 왕복,
psql 제약 확인, pytest 11개, ruff/pyright 클린, 라이브 API program 필터 검증)

## Problem

- 현재 동작: 신규 코드베이스에 `members` 테이블(4필드: name/email/program/subscribed)만 존재.
  캠페인·발송로그·참여 이벤트 테이블이 없어 발송도 추적도 불가능.
- 기대 동작: 발송(캠페인→회원별 로그)과 추적(Resend 웹훅 이벤트 적재)을 담을 수 있는
  4개 테이블이 Alembic 마이그레이션으로 로컬 Postgres에 적용된다.
- 왜 필요한가: 프로젝트 핵심 가치 "추적 → 점수 → 분류"의 데이터 기반.
  우선순위 4번(웹훅 엔드포인트)이 이 스키마를 전제로 함.

## Context

관련 파일·함수 (AI가 코드 찾는 시간을 줄이는 힌트):

- `app/models/member.py` — 참조 구현(수직 슬라이스). 새 모델은 이 패턴을 따른다.
- `archive/foodtech-hub-deploy/db.py` — 프로토타입 스키마. members 필드 목록·newsletters/send_logs 구조 이식 원본.
- `docs/erd.html` — ERD 초안 v0.2. 단, 추적 부분은 "자체 리다이렉트 토큰" 기준의 구버전 →
  **Resend 웹훅 기준으로 재설계된 본 티켓이 우선**.
- `migrations/versions/5d720a0e57b9_members_table.py` — 기존 마이그레이션 예시.

## Scope

허용:

- `app/models/` — member.py 확장, member_program.py / newsletter.py / send_log.py / engagement_event.py 신규, `__init__.py` 갱신
- `app/services/members.py`, `app/routes/members.py` — program 필터·생성 로직을 member_programs 조인 기반으로 변경 (기능 동일 유지)
- `migrations/versions/` — 신규 마이그레이션 1개
- `tests/` — 스키마 스모크 테스트 (테이블 생성·제약 검증) + 기존 members 테스트의 program 사용부 갱신

금지:

- 무관한 리팩터링
- 라우트/서비스 구현 (웹훅 엔드포인트는 T-003 별도 티켓)
- news_items / newsletter_news / score_snapshots (각자 기능 티켓에서)

## 설계 확정 사항

**members 확장** — 프로토타입 필드 이식: phone, category, subcategory, position,
organization, location, division, business_area, membership_status, membership_type,
payment_history, benefit_pct, council_label, unsubscribe_token(unique), notes, updated_at.
- 실명단 매핑(2026-07-12 `(260710)_회원_전체_명단.xlsx` 분석): 구분3(개인/단체)→membership_type,
  구분4(산업계/학계/기관/정부/언론/기타)→category, 구분5(스타트업/대기업 등)→subcategory.
- **email: nullable + non-unique 인덱스** — 실명단에 이메일 없는 회원(~6%)과 중복 이메일이 존재.
  중복 병합은 임포트 티켓 소관, 스키마에서 unique 금지.
- 기존 `program` 단일 컬럼과 cohort는 **member_programs로 이동** (아래).

**member_programs (신규)** — 회원↔프로그램 M:N. 실명단이 사람×프로그램 1행 구조(4,002행 vs
고유 이메일 3,240)라 단일 program 컬럼으로는 불가. 기수는 프로그램에 딸린 속성.
- member_id(FK, index), program(str — 실명단 구분1의 4개 값: 사업화교육/최고책임자과정/
  푸드테크학과/월드푸드테크협의회), cohort(str, nullable — 구분2 '원우(N기)' 등), created_at.
- unique(member_id, program). 발송 세그먼트 쿼리의 기준 테이블.

**newsletters** — subject, html_body, text_body, created_by, status(draft|sending|sent|failed, index),
target_filter(**jsonb**), total_recipients/sent_count/failed_count, created_at, sent_at.

**send_logs** — newsletter_id(FK, index), member_id(FK, nullable), email(index),
status(queued|sent|failed|bounced — `opened` 제거: 열람은 이벤트 테이블 소관),
provider_id(Resend 메시지 ID, **unique index** — 웹훅 email_id 역추적 조인 키), error, created_at.

**engagement_events** — id(bigserial), send_log_id/member_id/newsletter_id(FK, 수신 시점에
셋 다 해석해 저장 — Score의 회원×이벤트 조인을 위한 의도적 비정규화),
event_type(delivered|opened|clicked|bounced|complained|unsubscribed, index),
url(클릭된 URL, nullable), provider_event_id(**unique** — 웹훅 재시도 중복의 멱등 처리),
payload(jsonb, 원본 보존), occurred_at(웹훅의 발생 시각) / created_at(수신 시각), 전부 timestamptz.

인덱스: engagement_events(member_id, occurred_at), (newsletter_id, event_type).

## Acceptance Criteria

1. 새 Docker Postgres에서 `alembic upgrade head`가 에러 없이 통과한다.
2. 5개 테이블이 위 설계대로 생성된다 (unique 제약: send_logs.provider_id,
   engagement_events.provider_event_id, members.unsubscribe_token,
   member_programs(member_id, program) 복합 unique. members.email은 unique 아님).
3. `alembic downgrade -1`로 롤백이 가능하다.
4. 기존 기능(members CRUD, 기존 테스트)이 깨지지 않는다.

## Verification

1. `docker compose up -d` → `uv run alembic upgrade head` → 성공 확인
2. psql로 `\d engagement_events` 등 테이블 구조·인덱스 확인
3. `uv run pytest` 전체 통과
4. `uv run alembic downgrade -1` → `upgrade head` 재적용 왕복 확인
