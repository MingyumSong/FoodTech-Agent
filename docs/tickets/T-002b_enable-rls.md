# T-002b 전 테이블 RLS 활성화 (Supabase Security Advisor 대응)

Type: TASK
Status: DONE (2026-07-13 — 로컬·Supabase 양쪽 rowsecurity=true × 6, 왕복 검증, pytest 11개 통과.
Data API 비활성화(민겸)와 이중 방어. Security Advisor 0건은 사용자 Refresh 확인 대기)

## Problem

- 현재 동작: T-002로 만든 테이블 6개(alembic_version 포함)가 RLS 꺼진 채 생성됨.
  Supabase Security Advisor에서 "RLS Disabled in Public" 에러 6건 —
  publishable 키만 있으면 PostgREST로 테이블 전체 조회 가능한 상태였음.
- 기대 동작: 모든 테이블 RLS 활성화(정책 없음 = 전면 거부). 앱은 테이블 소유자
  직접 접속이라 영향 없음. 대시보드 Data API 비활성화(민겸, 2026-07-13 완료)와 이중 방어.
- 왜 필요한가: members에 회원 3,000명 PII가 들어가기 전에 닫아야 함.

## Context

- `migrations/versions/` — 신규 리비전 (autogenerate 불가 — RLS는 모델에 없는 속성이라 수동 작성)
- `.claude/rules/alembic-migrations.md` — 재발 방지 규칙 추가 대상
- 적용: 로컬 → `scripts/db_target.sh supabase`로 운영

## Scope

허용:
- `migrations/versions/` 신규 리비전 1개
- `.claude/rules/alembic-migrations.md` 규칙 1줄 추가

금지:
- RLS 정책(policy) 생성 — 정책 없는 전면 거부가 의도된 상태
- 모델 파일 수정 (변경 없음)

## Acceptance Criteria

1. 로컬·Supabase 양쪽에서 `pg_tables.rowsecurity = true` × 6개 테이블.
2. `alembic downgrade -1` 왕복 가능.
3. 기존 테스트 전체 통과 (앱 동작 무영향 확인).
4. Supabase Security Advisor 에러 0건 (Refresh 후 사용자 확인).
5. 규칙 파일에 "신규 테이블 마이그레이션은 ENABLE ROW LEVEL SECURITY 포함" 명시.

## Verification

1. `uv run alembic upgrade head` → 로컬 psql `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public'`
2. `uv run pytest -q` 통과
3. `echo supabase | scripts/db_target.sh supabase uv run alembic upgrade head` → 동일 쿼리로 확인
