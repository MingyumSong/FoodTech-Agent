# T-026 대시보드와 DB 통합 — 두 Supabase 프로젝트를 하나로

Type: TASK
Status: TODO (⚠️ 실행 전 결정 3건 필요 — 아래 "결정이 필요한 것")

## Problem

- **현재 동작:** 회원 데이터가 **서로 다른 Postgres 두 곳**에 갈라져 있다.

  | | 프로젝트 ref | 계정 | 사람 테이블 |
  | --- | --- | --- | --- |
  | 뉴스레터(이 레포) | `wywegrnidfwjuozmfgbd` | 교수님(snupfm@gmail.com) | `members` 3,413 |
  | 대시보드 | `rfeffxzeqxcpareyczbt` | 희정님 | `people` 1,463 |

  둘 다 Supabase지만 **별개 인스턴스라 JOIN이 불가능하다.** 대시보드가 참여도를 쓰려고
  `functions/api/newsletter-scores.js`에서 우리 `/admin/scores.csv`를 HTTP로 긁어가는 이유가 이것이다.

- **기대 동작:** 사람이 한 곳에 있고, "이번 행사 발표자 중 뉴스레터 참여도 상위"를 쿼리 한 번으로 묻는다.

- **왜 필요한가:** 실측 대조(2026-08-12) 결과 **763명이 양쪽에 중복 존재**한다.
  양쪽에서 각자 수정되면 갈라지고, 갈라진 뒤엔 어느 쪽이 맞는지 판정할 근거가 없다.
  지금은 데이터가 작아서(우리 DB **16MB**, 참여 이벤트 1,123·발송기록 419) 이전 비용이 최저다.
  본 발송이 시작되면 `send_logs`가 **주당 3,413행**씩 쌓이고, 그때부터는 라이브 발송 중 이전이 된다.

### 실측 대조 (2026-08-12)

```
우리 members (이메일 보유)   3,208
저쪽 people  (전체)          1,463   (이메일 보유 924)

이메일로 정확히 겹침           763
우리에만 있음                2,445   ← 우리 명단이 3배 크다
저쪽에만 있음                  161

이름 같은데 이메일 불일치      131   ← 사람이 판정해야 함
이메일 같은데 이름 다름          4   ← 개별 확인
우리 쪽 동명이인(이메일 2+)    315
```

**자동 병합은 불가능하다.** 이름 기반 자동 매칭을 돌리면 131 + 315명이 잘못 붙는다.

두 데이터는 축이 다르다 — 저쪽은 **깊이**(소속 조직 관계, 행사 발표 이력 `event_presentations`,
프로젝트 참여), 우리는 **넓이**(3,208명)와 **행동 이력**(발송·클릭·반응).

## Context

- 우리 접속 정보: `.env`의 `SUPABASE_URL`(pooler URL — 사용자명에 project ref가 들어 있다).
- 저쪽 스키마: `HeejeongH/foodtech-dashboard`의 `supabase_schema.sql`
  — 13테이블 + RPC 26개. `organizations / people / education_programs / program_cohorts /
  program_enrollments / wftc_memberships / events / event_presentations / foodtech_domains /
  projects / project_participants / project_organizations / activity_logs`.
- 우리 스키마: Alembic 마이그레이션이 단일 진실. 8테이블.
- **규칙 C3가 이 작업을 위해 존재한다** — "Supabase 특화 기능 금지, 어떤 Postgres 호스팅으로든
  옮길 수 있어야 한다." RLS 외에 Supabase 특화 기능을 안 썼으므로 `pg_dump`/`restore`로 끝난다.
- 대시보드는 정적 사이트(Cloudflare Pages) + PostgREST/RPC. 우리는 FastAPI(Railway) + DB 직결.

## 결정이 필요한 것 (이게 정해지기 전엔 실행하지 않는다)

**① 어느 Postgres가 집인가**

- (A) 저쪽 프로젝트로 우리가 간다 — 대시보드 재설정이 필요 없다. 단 **희정님 개인 계정**이다.
- (B) 우리 프로젝트로 저쪽이 온다 — 대시보드의 URL/anon key/RPC를 전부 재설정해야 한다.
- (C) **기관 계정에 새 프로젝트를 만들고 둘 다 간다** — 규칙 C3의 "기관 org 이관"이 어차피
  예정돼 있다. (A)나 (B)는 개인 계정에서 개인 계정으로 옮기는 것이라 **중간 기착지를 하나 더
  만드는 셈**이다. 한 번에 끝내려면 (C).

**② 본 발송 전인가 후인가** — 지금이 데이터가 제일 작아 싸지만, 8/13 본 발송이 밀릴 수 있다.
Activity Score가 의미를 가지려면 발송 데이터 포인트가 2~3개 필요하고 남은 목요일은 3번뿐이다.

**③ 저쪽 보안 정리가 선결인가** — 아래 참조. **(A)를 고를 경우 이건 선결이다.**

## 선결 조건 — 저쪽 프로젝트 보안 (희정님 몫)

`supabase_schema.sql` 마지막 블록이 13개 테이블 전부에 다음을 건다:

```sql
CREATE POLICY "public_read"  ON %I FOR SELECT USING (true)
CREATE POLICY "public_write" ON %I FOR ALL    USING (true) WITH CHECK (true)
```

`FOR ALL`이라 익명 사용자가 **읽기뿐 아니라 수정·삭제까지** 가능하다. 그리고 프로젝트 URL과
anon key가 **public 레포에 커밋돼 있다**(`config.js`, `functions/api/agent.js`).
`data/people.csv`에는 1,471명·이메일 965·전화 925가 들어 있다.

→ **이 상태의 프로젝트에 우리 회원 3,413명을 넣으면 안 된다.**

## Scope

허용:

- `alembic/` 설정(`version_table_schema` 등), `app/config.py`, `scripts/` 이전 도구
- 새 마이그레이션(사람 연결 테이블) — **기존 리비전 편집 금지**
- `docs/` 이전 절차·검증 기록

금지:

- **발송 엔진을 대시보드로 옮기는 것.** Resend 웹훅 수신(서명 검증), 07:00·13:00 크론,
  LLM 수집·분류, 실제 발송은 서버가 필요하다. Railway에 남는다.
- **`public` 스키마에 우리 테이블을 넣는 것** (아래 1단계 참조)
- **자동 사람 병합** — 131 + 315명이 잘못 붙는다
- `PUBLIC_BASE_URL` 변경 — 이미 나간 메일의 수신거부·반응 링크 기준이다
- 저쪽 레포 수정 (읽기 권한만 있고, 소유자는 희정님)

## 단계 — 데이터 이전과 사람 병합을 분리한다

이 둘을 한 번에 하려는 것이 이런 작업이 실패하는 전형적 방식이다.
**1단계는 반나절이고 되돌릴 수 있다. 3단계는 오래 걸리고 되돌리기 어렵다.**

### 1단계 · DB만 옮긴다 (되돌릴 수 있음)

**우리 8테이블을 `public`이 아니라 `newsletter` 스키마에 넣는다.** 그리고 Supabase의
PostgREST 노출 스키마 목록에서 `newsletter`를 뺀다.

이유: 저쪽 `public`은 이미 익명에게 전부 열려 있고, 그 정책은 **테이블 이름을 배열로
하드코딩해 도는 `DO $$ LOOP`** 다. 누가 나중에 "전 테이블"로 한 줄만 바꾸면 우리 회원
3,413명의 이메일이 그대로 공개된다. 스키마를 나누면 그 사고가 구조적으로 불가능해진다.

순서는 규칙대로 **DB 먼저, 코드 나중**:

```
pg_dump(우리) → 대상 프로젝트의 newsletter 스키마로 restore
→ 8테이블 행수 대조 → DATABASE_URL 교체 → railway up → /admin/status 확인
```

챙길 것: Alembic `version_table_schema`, `search_path`, 크론 07:00·13:00을 피한 시간대,
pooler URL이 아닌 직결 URL이 필요한지 확인.

**롤백**: 기존 프로젝트를 며칠 그대로 둔다. 되돌리기는 `DATABASE_URL` 한 줄.

### 2단계 · 사람은 '연결'만 한다 (아무것도 지우지 않음)

`newsletter.person_link(member_id, person_id, method, confidence)` 매핑 테이블만 만든다.

- 763건: 이메일 정확 일치 → 자동
- 131건 + 4건: **미리보기 후 컨펌하는 dry_run 게이트**로 사람이 판정
  (T-007 임포터에서 동명이인 54명을 구제한 그 패턴)

병합도 삭제도 없어서 언제든 되돌아간다.

### 3단계 · 방향 정하고 흡수 (되돌리기 어려움)

- 저쪽에만 있는 161명 → 우리 `members`로 (뉴스레터 대상이 되려면)
- 우리에만 있는 2,445명 → 저쪽 `people`로 보낼지는 대시보드가 "World FoodTech Database"를
  지향하는지에 달렸다

**1·2단계가 안정된 뒤에만.**

### 4단계 · UI 수렴

우리 `/admin/*`은 두고 대시보드에 API를 제공한다. 이미 `newsletter-scores.js`가 그 패턴이다.
단 지금 그 함수는 인증이 없어 이름·이메일이 공개된다 — 별건으로 정리(아래 참조).

## Acceptance Criteria

1. 결정 ①②③이 문서로 확정된 뒤에 착수한다.
2. 1단계 후 `/admin/status`의 회원 수·발송 수·이벤트 수가 이전 전과 **정확히 일치**한다.
3. 우리 테이블이 PostgREST로 **노출되지 않는다**(익명 요청이 데이터를 못 받는다).
4. 이전 후 첫 파일럿 발송이 정상 동작한다(조립 → 발송 → 웹훅 수신 → 참여도 반영).
5. 2단계에서 사람이 확인하지 않은 매칭은 저장되지 않는다.
6. 기존 기능이 깨지지 않는다.

## Verification

1. `bash scripts/check.sh` 통과.
2. 이전 직후 8테이블 전부 행수 대조(before/after 스크립트 출력을 티켓에 붙인다).
3. 익명으로 PostgREST를 찔러 우리 테이블이 안 보이는지 확인 —
   상태코드가 아니라 **응답 본문**으로 판정한다.
4. 이전 다음 날 13:00 발송이 정상인지 `/admin/status`와 실제 수신으로 확인.
5. 롤백 리허설: `DATABASE_URL`을 옛 프로젝트로 되돌렸을 때 정상 동작하는지 한 번 해본다.

## 관련 — 이 티켓과 별개로 처리할 것

- **`ADMIN_TOKEN`이 대시보드에 통째로 넘어가 있다.** `NEWSLETTER_ADMIN_TOKEN`으로 Cloudflare에
  설정된 그 토큰은 `/admin/scores.csv`뿐 아니라 `/admin/members`(3,413명 PII)와
  **`/admin/review/send`(발송 실행)** 도 연다. → 점수 전용 읽기 토큰 분리 + 토큰 로테이션.
- `/api/newsletter-scores`는 인증이 없어 **회원 이름·이메일이 공개**된다
  (우리 `CSV_COLUMNS`에 둘 다 있다). → CSV에서 PII를 빼는 옵션.
