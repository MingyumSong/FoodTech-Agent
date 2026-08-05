# T-023: Activity Score 활용 — 등급 기반 명단 추출·발송 대상 선정

Type: FEAT
Status: **PARTIAL** (2026-08-06 — CSV 명단 추출은 완료·배포. **등급 발송은 메커니즘만 있고
관리자가 쓸 진입점이 없다** — Scope 1·2의 UI 항목 미구현. 상세는 아래 "남은 일")

구현 중 **발송이 자기 수신자 목록을 바꾸는 결함**을 발견해 설계를 바꿨다 — 아래 검증 결과 참조.

## Problem

- 현재 동작: Activity Score가 계산되고(T-017) 관리자 화면에 표시된다(T-019).
  하지만 **점수로 할 수 있는 일이 "보는 것"뿐**이다. 확인한 사실:
  - **명단을 꺼낼 수 없다.** `app/routes/members.py`에 CSV **가져오기**만 있고 내보내기가 없다.
    교수님이 "활발 회원에게 행사 안내 보내자"고 하면 화면을 보고 손으로 옮겨 적어야 한다.
  - **등급으로 발송 대상을 고를 수 없다.** `newsletter._recipients`는 `program` 하나로만
    수신자를 정한다. `active` 회원에게만 보내는 경로가 없다 — **분류를 해놓고 분류대로 못 보낸다.**
- 기대 동작: 등급으로 회원을 걸러 **명단을 파일로 받거나**, 그 등급에게만 발송할 수 있다.
- 왜 필요한가: 프로젝트 목표가 "**참여율 높은 회원에게 행사·베네핏 부여**"이고(CLAUDE.md 동기),
  Score는 그 선별 근거로 만든 것이다. 꺼내 쓸 방법이 없으면 Score는 보기 좋은 숫자로 남는다.

## Context (코드로 확인한 사실)

- `app/services/activity_score.py`
  - `score_members(session, member_ids)` — **배치 쿼리 3회**로 묶음 계산. 회원 수가 늘어도
    왕복이 늘지 않는다. 등급 필터는 이 함수 결과를 거르기만 하면 된다.
  - `tier_for()` 등급: `active`/`warm`/`dormant`/`unknown`/`unsubscribed`.
  - `percentile_ranks()` — 저장하지 않고 조회 시점 계산.
- `app/services/admin_pages.py:409 collect_scores` — 참여도 탭이 쓰는 행 생성기.
  **이메일이 없다**(name/score/tier/percentile/sends/…). 명단 추출엔 이메일이 필수라 보강 필요.
  대상은 `pilot_members` 전원 — 지금은 파일럿 25명.
- `app/services/newsletter.py:133 _recipients(session, program)` — 발송 대상 선정.
  `target_filter`(JSONB)는 이미 `{"program": ...}`을 담는 **기존 메커니즘**이라
  `tiers`를 얹는 게 자연스럽다. `send_newsletter`가 이 값을 읽어 수신자를 정한다.
- 100명 가드(`PILOT_MAX_RECIPIENTS`)와 멱등(`send_logs`)은 수신자 목록과 무관하게 동작한다 —
  등급 필터는 **목록을 좁히기만** 하므로 두 안전장치를 건드리지 않는다.
- 관리자 인증은 Basic(`require_admin_basic`) 임시. PII 노출 경로는 전부 이 뒤에 둔다(C6).
- 메모리 노트: `sqlmodel`의 `select`는 컬럼 4개까지만 타입이 잡힌다 — 넘치면 쿼리를 쪼갠다.

## Scope

허용:

1. `app/services/admin_pages.py`
   - `collect_scores`에 이메일 추가(배치 조회 1회). ✅
   - `scores_csv(session, *, tiers)` — 등급으로 거른 CSV 문자열 생성. ✅
   - ~~발송검토 탭에 **대상 등급 선택 UI**(체크박스, 미선택=전원).~~ ❌ **미구현**
2. `app/routes/admin.py`
   - `GET /admin/scores.csv?tier=active&tier=warm` — Basic 인증, CSV 다운로드. ✅
   - ~~발송검토의 초안 생성에 선택 등급을 전달.~~ ❌ **미구현**
3. `app/services/newsletter.py`
   - `_recipients(session, program, *, tiers=None)` — `tiers`가 없으면 **현행 그대로**.
   - `build_newsletter(..., tiers=None)` → `target_filter`에 `tiers` 저장.
   - `send_newsletter`가 `target_filter.tiers`를 읽어 수신자를 좁힌다.
4. `tests/test_score_targeting.py` 신규.
5. 이 티켓 파일.

금지:

- DB 스키마 변경 — `target_filter`(JSONB)에 키를 얹는다.
- **100명 가드·멱등·`_recipients`의 기존 조건(구독·이메일 보유·중복 제거) 변경 금지.**
- 파일럿 자동 발송(`build_pilot_daily`)의 대상 변경 — **전원 발송을 유지한다.**
  파일럿은 점수 산출용 실데이터를 모으는 중이라 대상을 좁히면 표본이 죽는다.
- Activity Score 공식·상수 수정(T-017 소관).
- 전체 3,413명 확장 — 발송 이력이 없어 전원 `unknown`이다. 본 발송 이후 별도 티켓.
- 관리자 인증 방식 변경(매직링크는 별도), archive/ 수정(C5), Supabase 특화 기능(C3).

## Acceptance Criteria

- [x] AC1: `/admin/scores.csv`가 이름·이메일·점수·등급·백분위·발송수·참여수를 담은 CSV를 준다.
- [x] AC2: `?tier=active&tier=warm`으로 등급을 거를 수 있고, 없으면 전원이 나온다.
- [x] AC3: CSV가 Basic 인증 없이는 401 — PII가 인증 밖으로 새지 않는다.
- [x] AC4: 한글 이름이 Excel에서 깨지지 않는다(UTF-8 BOM).
- [x] AC5: `tiers`를 준 발송은 해당 등급 회원에게만 간다 — 다른 등급은 `send_logs`에 안 남는다.
- [x] AC6: `tiers`가 없으면 수신자 목록이 **기존과 완전히 동일**하다(회귀 방어).
- [x] AC7: 등급으로 좁혀도 100명 가드·멱등이 그대로 동작한다.
- [x] AC8: 파일럿 자동 발송은 여전히 세그먼트 전원에게 간다.
- [x] AC9: `bash scripts/check.sh` 통과.
- [x] AC10(추가): **발송이 자기 수신자 목록을 바꾸지 않는다** — 아래에서 발견해 추가.

## Verification

1. `uv run pytest tests/test_score_targeting.py -q` — AC1~AC8 단위 테스트.
2. `bash scripts/check.sh` 전체 통과 (`exit=$?` 명시 확인 — 파이프가 종료코드를 삼킨다).
3. 로컬 서버에서 `/admin/scores.csv` 실제 다운로드 → 한글·이메일 확인, 인증 없이 401 확인.
4. 배포 후 운영에서 미인증 401 확인(본문으로 라우트 실재 확인 — 상태코드만으로는 판별 불가).

## 검증 결과 (2026-08-06)

`tests/test_score_targeting.py` 17개 통과, 전체 스위트 192개 통과. ruff·pyright 클린.

운영 실데이터(읽기 전용, PII 미출력): 전원 25행 / `active` 7행 / `active,warm` 15행.
한글 이름·BOM·등급 한글 라벨 정상.

### 구현 중 결함 발견 — 발송이 자기 수신자 목록을 바꿨다

처음엔 등급을 **발송 시점**에 계산했다. 테스트에서 이렇게 나왔다:

```
tier filter: 2 → 1   (첫 발송)
tier filter: 2 → 0   (재발송 — 대상이 사라짐)
```

첫 발송이 `send_logs`에 **무반응 1건**을 더하면서 점수가 활발 컷 아래로 내려간 것이다.
발송이 끝나자마자 그 사람은 더 이상 `active`가 아니다. 그래서:

- 발송이 중간에 실패해 재시도하면 **받아야 할 사람이 영영 빠진다**(멱등 재호출이 대상을 잃음).
- 같은 편의 수신자가 호출 시점마다 달라져 "누구에게 갔는가"를 재현할 수 없다.

→ **대상은 조립 시점에 확정한다**(`_target_filter`). `target_filter`에 `member_ids`를 얼려
저장하고 발송은 그 목록으로 좁히기만 한다. 100명 가드가 있어 목록 크기는 제한적이다.

**수신거부만은 얼리지 않는다.** 발송 시점에 `_recipients`로 다시 확인한 목록과 **교집합**을
취한다 — 조립 후 해지한 사람이 얼린 목록 때문에 되살아나면 안 된다. 회귀 테스트 2개로 고정했다.

### 설계 메모

- `_recipients(tiers=None)`은 **한 줄도 바뀌지 않은 경로**를 탄다(AC6). 등급을 안 주면
  점수 계산 자체가 일어나지 않는다.
- 등급 필터는 목록을 **좁히기만** 하므로 100명 가드·멱등(`send_logs` 기준)은 그대로다.
- 파일럿 자동 발송은 의도적으로 전원 유지 — 점수 산출용 표본을 깎으면 안 된다(AC8).

### 남은 일 — 등급 발송에 진입점이 없다 (2026-08-06 세션 랩에서 발견)

`build_newsletter(..., tiers=[...])`는 동작하고 테스트도 있지만, **`tiers`를 넘기는 프로덕션
코드가 한 줄도 없다.** 유일한 호출부인 `app/routes/jobs.py:48`이 인자를 안 넘기고,
발송검토 탭에도 등급 선택 UI가 없다. 즉 **관리자가 등급 발송을 실행할 방법이 없다.**

Scope에 UI를 적어놓고 구현하지 않은 채 DONE으로 닫았던 것을 바로잡는다. 남은 작업:

- 발송검토 탭에 등급 체크박스(미선택=전원) → `admin_review_build`가 `tiers`를 넘기도록
- 또는 `/jobs/newsletter-build`에 `tiers` 쿼리 파라미터

**단 지금 급하지 않다** — 파일럿 25명은 전원 발송이고, 행사 안내 같은 비뉴스 메일을 만드는
기능 자체가 없다. 당장 값을 내는 건 CSV 명단 추출이고 그건 완료됐다.
본 발송이 시작돼 "활발 회원에게만" 보낼 일이 생길 때 붙이면 된다.

## 참고

- 등급 기반 **발송**은 지금 당장 쓸 곳이 없다 — 파일럿 25명은 전원 발송이고, 행사 안내 같은
  비뉴스 메일을 만드는 기능도 없다. 본 발송이 시작되면 필요해지는 메커니즘이라 미리 깔아둔다.
  당장 값을 내는 건 **CSV 명단 추출**이다.
- 관련: T-022(롤업 배치화)는 확대 발송 전 필수. 이 티켓과 독립.
