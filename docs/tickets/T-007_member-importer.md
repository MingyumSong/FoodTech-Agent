# T-007: 회원 임포터 — 구글시트 CSV/XLSX 업서트

Status: DONE (2026-07-18 — AC 8/8 충족, 테스트 57개 통과. 라이브: CLI dry-run→실행(created 2)→
재실행(created 0, updated 2, 중복 연결 0) 멱등 확인. 산출물: app/services/member_import.py,
POST /api/members/import, scripts/import_members.py. 실명단 임포트는 파일럿 세그먼트 선정 때 수행.)

## Problem

회원 3,000명 명단이 구글시트에 있고 DB는 비어 있다. 파일럿 세그먼트 선정(3주차)과
발송의 전제. 운영 방식은 결정 1: **구글시트 = 직원 편집용 유지, 주기적으로 임포트**.
따라서 1회성 이관이 아니라 **반복 실행해도 안전한 동기화 도구**여야 한다.

## Context

- 프로토타입 `archive/foodtech-hub-deploy/import_members.py`에서 로직 참고(재작성):
  한글 헤더 매핑, 헤더 행 자동탐지(제목 행 스킵), 인코딩 자동감지(utf-8/cp949/euc-kr).
- T-002 스키마 주석: **실명단에 이메일 결측(~6%)·중복 존재 → email unique 금지, 병합은 임포트 소관.**
- 시트는 프로그램별 명단이므로 `program`은 컬럼이 아니라 **임포트 파라미터**
  (예: program=최고책임자과정) → `member_programs`에 연결(cohort는 소분류 컬럼).
- `/api/members` 라우터는 ADMIN_TOKEN 잠금 완료 — 임포트 엔드포인트도 자동 보호.

### 설계 결정 — "유지보수 쉽게"의 구체화

1. **업서트 멱등**: 매칭 순서 email → (name+organization) → 신규 생성.
   같은 파일 재임포트 = created 0, updated N. 시트 수정 → 재업로드가 유일한 운영 루틴.
2. **빈 칸은 기존 값을 지우지 않는다** (None은 스킵) — 시트 일부 컬럼만 채워도 안전.
3. **삭제는 자동으로 하지 않는다** — 시트에서 빠진 회원은 건드리지 않음(대량 삭제 사고 방지).
   탈퇴 처리는 membership_status 컬럼 값으로 표현하거나 관리자 화면(추후)에서 개별 처리.
4. **dry_run 미리보기**: `?dry_run=true`면 DB에 쓰지 않고 결과 리포트만 반환 —
   "올리기 전에 몇 명이 추가/변경되는지" 확인하는 습관을 기본 운영 절차로.
5. **리포트 상세**: created/updated/skipped(이름 없음)/errors(행 번호+사유) + 감지된 인코딩·헤더.
6. 구글시트 API 직접 연동(버튼 클릭 동기화)은 서비스 계정 세팅이 필요해 **후속 티켓** —
   당분간 운영 루틴: 시트에서 파일 다운로드 → 업로드(API 또는 CLI).

## Scope

- `docs/tickets/T-007_member-importer.md` (이 파일)
- 의존성: `uv add openpyxl python-multipart`
- `app/services/member_import.py` (신설) — 파싱·정제·업서트·리포트
- `app/routes/members.py` — `POST /api/members/import` (multipart 파일 업로드, dry_run 파라미터)
- `scripts/import_members.py` (신설) — CLI 래퍼 (로컬/운영 DB 직접 실행용)
- `tests/test_member_import.py` (신설)
- Scope 밖: 구글시트 API 연동, 관리자 화면, 세그먼트 선정 로직, 삭제 동기화

## Acceptance Criteria

- [x] AC1: CSV(utf-8/cp949)·XLSX 모두 임포트 — 인코딩·헤더 행 자동감지, 한글 헤더 매핑
- [x] AC2: 업서트 멱등 — 같은 파일 2회 임포트 시 두 번째는 created=0, 중복 행 없음
- [x] AC3: email 결측 행도 저장되고 (name+organization)으로 재임포트 시 매칭됨
- [x] AC4: `dry_run=true` → DB 무변경 + 리포트는 실제와 동일 수치
- [x] AC5: program 파라미터 지정 시 member_programs 연결(중복 연결 없음), cohort=소분류
- [x] AC6: 빈 셀이 기존 값을 덮어쓰지 않음
- [x] AC7: `bash scripts/check.sh` 통과 ✅ 57 passed
- [x] AC8 (라이브): 합성 샘플로 CLI dry-run→실행→재실행 멱등 확인 ✅ 2026-07-18

## Verification

```bash
bash scripts/check.sh
# 로컬 라이브(AC8): 샘플 CSV로
uv run python scripts/import_members.py sample.csv --program "최고책임자과정" --dry-run
uv run python scripts/import_members.py sample.csv --program "최고책임자과정"
uv run python scripts/import_members.py sample.csv --program "최고책임자과정"  # → created=0 확인
```

## Notes

- 실명단(PII)은 레포에 커밋 금지 — 테스트는 합성 데이터만 사용 (C6).
- 운영 임포트는 배포 후 API(`POST /api/members/import` + ADMIN_TOKEN)로, 또는
  `DATABASE_URL=$SUPABASE_URL` 환경에서 CLI로.
