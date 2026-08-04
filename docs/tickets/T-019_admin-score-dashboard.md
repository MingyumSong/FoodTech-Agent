# T-019 관리자 참여도 탭 — 세그먼트 스코어 대시보드

Type: FEAT
Status: DONE (2026-08-04 구현·검증·**배포 완료** — 커밋 cc68578)

## Problem

- 현재 동작: Activity Score(T-017)가 계산은 되지만 **볼 수 있는 곳이 없다.**
  `pilot_members.activity_score`에 값이 들어갈 뿐, 관리자 화면 어디에도 노출되지 않는다.
- 기대 동작: 관리자 탭에서 **누가 활발하고 누가 잠잠한지**, 그리고 **세그먼트별로 어디가
  반응이 좋은지**를 한 화면에서 본다.
- 왜 필요한가: 점수의 용도가 "행사·베네핏 대상 선별"인데, 그 판단을 하는 사람(희정·교수님)이
  DB를 못 본다. 로드맵의 다음 항목이고, T-017을 실제로 쓸 수 있게 만드는 마지막 한 칸이다.

## 설계 메모

### 점수는 저장값이 아니라 **조회 시점에 계산**한다

`pilot_members`의 점수 컬럼은 발송 잡이 돌 때만 갱신된다. 운영 DB를 확인해보니
**2026-08-04 22:37 기준 25명 전원 `activity_score=0`, `activity_tier=NULL`,
`score_updated_at=NULL`** — T-017 배포가 오늘 발송(06:26 UTC) 이후라 아직 한 번도 롤업되지 않았다.
저장값을 그대로 그리면 화면이 전원 0점으로 뜬다.

→ 화면은 `score_members(session, ids)`로 **매번 새로 계산**한다. 25명 기준 배치 쿼리 3회라 싸고,
크론 성공 여부와 무관하게 항상 현재 진실을 보여준다. `pilot_members`의 컬럼은 그대로 두고
**이력 스냅샷** 역할만 맡긴다(나중에 "지난주 대비 상승/하락"을 만들 때 필요한 값이다).

### 세그먼트 축

`pilot_members`에 이미 채워져 있는 3축을 쓴다(25명 전원 값 있음):

| 축 | 값 | 쓸모 |
| --- | --- | --- |
| `group_no` | 1~5 (각 5명) | **A/B 그룹** — T-016 착지 페이지 실험의 대조군 비교에 그대로 쓰인다 |
| `org_type` | 개인 15 / 기관 10 | 소속 유형별 반응 차이 |
| `program` | 계약학과 21 / 협의회 4 | 프로그램별 반응 차이 |

세그먼트 표본이 작으므로(4~21명) **평균과 함께 인원 수를 항상 같이 표시한다** — n=4짜리 평균을
n=21과 나란히 놓으면 오독하기 쉽다.

### 화면 구성

1. **등급 분포** — active/warm/dormant/unknown 바 + 중위·평균 점수.
2. **세그먼트별 평균** — 위 3축, 각 행에 `평균 점수 · 인원 · active 수`.
3. **회원 순위표** — 이름·점수·백분위·등급·발송/반응/클릭 편수·마지막 참여일. 점수 내림차순.
4. **해석 주의** — 상대 순위 도구라는 점, 봇 열람 제외 사실, `unknown`이 "안 보낸 사람"이라는 점.

PII(이름)는 인증 뒤 화면이라 표시하되 로그엔 남기지 않는다(C6, 회원관리 탭과 같은 원칙).

## Context

관련 파일·함수:

- `app/services/activity_score.py` — `score_members(session, ids) -> {id: ScoreResult}`,
  `percentile_ranks(scores)`, `ScoreResult(score/tier/window_sends/engaged_sends/clicked_sends/
  last_engaged_at)`, 상수 `ACTIVE_CUT`/`WARM_CUT`/`HALF_LIFE_DAYS`/`BOT_OPEN_SECONDS`.
- `app/services/admin_pages.py` — `_TABS`(탭 추가 지점), `_shell`/`_nav`, `_CARD`,
  `collect_popular`/`render_popular_page`(collect→render 2단 분리 패턴이 이 탭의 본), `_dwell_card`.
- `app/services/admin_status.py` — `_bar_rows(pairs, total, label_map)`, 팔레트
  `ACCENT`/`INK`/`GRAY`/`GRAY_SOFT`/`LINE`/`BG`/`FONT`.
- `app/routes/admin.py` — `require_admin_basic`, `admin_popular`(읽기 전용 탭 라우트의 본).
- `app/models/pilot_member.py` — 세그먼트 컬럼 `group_no`/`org_type`/`program`, 이름 스냅샷.
- `tests/test_admin_pages.py` — `_auth()`, `monkeypatch`로 `settings.admin_token` 주입하는 패턴.

## Scope

허용:

- `app/services/admin_pages.py` — `collect_scores`/`render_scores_page` 추가, `_TABS`에 탭 1줄 추가.
- `app/routes/admin.py` — `GET /admin/scores` 추가.
- `tests/test_admin_pages.py` — 이 탭 테스트 추가.
- `docs/tickets/T-019_admin-score-dashboard.md` (이 파일).

금지:

- DB 스키마 변경. `pilot_members` 컬럼은 읽지도 쓰지도 않는다(점수는 조회 시 계산).
- `activity_score.py`의 계산 로직·상수 수정 (읽어 쓰기만 한다).
- 전체 3,421명 확장 — 이 탭은 파일럿 25명 대상.
- 쓰기 동작(발송·수정 버튼) 추가 — 읽기 전용 탭.
- 무관한 리팩터링, archive/ 수정(C5), Supabase 특화 기능(C3).

## Acceptance Criteria

1. `GET /admin/scores`가 인증 없이는 401, Basic 인증 후 200 HTML을 준다.
2. 등급 분포·중위/평균 점수가 표시된다.
3. 세그먼트 3축(그룹/소속 유형/프로그램)별 평균 점수가 **인원 수와 함께** 표시된다.
4. 회원 순위표가 점수 내림차순이고, 각 행에 백분위·등급·발송/반응/클릭 편수가 있다.
5. 점수는 `pilot_members`의 저장값이 아니라 조회 시점 계산값이다 —
   저장값이 0인 상태에서도 실제 참여가 있으면 0이 아닌 점수가 화면에 나온다.
6. 파일럿 회원이 한 명도 없을 때 빈 화면 대신 안내 문구가 나온다(터지지 않는다).
7. 탭 내비게이션에 "참여도"가 추가되고 기존 탭 4개가 그대로 동작한다.
8. 기존 기능이 깨지지 않는다 — `bash scripts/check.sh` 통과.

## Verification

1. `uv run pytest tests/test_admin_pages.py -q` 통과.
2. `bash scripts/check.sh` 전체 통과(파이프에 종료코드가 삼켜지지 않게 `exit=$?` 확인).
3. **스크린샷 검수** — 로컬 서버를 띄우고 헤드리스 크롬으로 `/admin/scores`를 캡처해
   직접 보고 레이아웃을 고친 뒤 전달한다(시각 산출물은 눈으로 보기 전에 완료라 하지 않는다).
4. 운영 데이터로 렌더 검수 — 읽기 전용으로 Supabase 실데이터를 붙여 25명이 실제로
   어떻게 보이는지 확인(쓰기 없음).

## 검증 결과 (2026-08-04)

1. `tests/test_admin_pages.py` 15개 통과(참여도 탭 5개 신규), 전체 153개 통과. ruff·pyright 클린.
2. 운영 데이터 렌더 + 헤드리스 크롬 스크린샷 검수 완료. 실제 산출:
   - 등급 **활발 6 / 관심 9 / 잠잠 10**, 중위 14.6 · 평균 17.4.
   - 발송 그룹: 1조 24.6 > 4조 23.2 > 5조 17.4 > 3조 11.1 > 2조 10.6 (각 5명).
     **그룹 간 격차가 2배 이상** — T-016 A/B를 이 그룹으로 돌릴 때 대조군을 그냥 고르면 안 된다는
     신호다(사전 참여도가 다르므로 짝을 맞춰야 한다).
   - 소속 유형: 기관 20.0(10명) > 개인 15.6(15명). 프로그램: 계약학과 17.6(21명) ≈ 협의회 16.4(4명).
3. **스크린샷 검수에서 고친 것**: 세그먼트 축마다 막대를 자기 최대에 맞춰 그리는 바람에
   그룹 24.6과 프로그램 17.6이 **둘 다 꽉 찬 막대**로 보였다 → 세 축이 **공통 스케일**을 쓰도록
   바꾸고 카드 3개를 1개로 합쳤다. 숫자를 안 읽고 막대만 보면 정반대로 읽히던 문제.
4. AC5 확인: 현재 운영 DB의 `pilot_members.activity_score`는 전원 0·tier NULL인데
   화면에는 0이 아닌 점수가 정상 표시된다 = 저장값이 아니라 조회 시점 계산이 맞다.

### 배포 검증 (2026-08-04 23:0x KST, `railway up`)

스키마 변경이 없어 마이그레이션 선행은 해당 없음(C2).

- `/openapi.json`에 `/admin/scores` 등장 = 신 코드 기동 확인(배포 후 약 40초).
- `/health` → `{"status":"ok","db":"ok"}`.
- 미인증 `/admin/scores` → **401**(핸들러 본체 미실행, 부작용 없는 프로브).
- Basic 인증 → **200**, 본문에 참여도 분포·세그먼트별 평균·회원별 참여도·발송 그룹 모두 존재.
  응답 크기 30,205바이트로 로컬 렌더와 일치 = 같은 데이터·같은 템플릿.

### 남은 일
- 전체 회원 확장·"지난주 대비 변화"는 별도 티켓(후자를 하려면 `pilot_members`의 저장 점수가
  이력으로 쌓여야 하므로 크론이 며칠 돈 뒤에 착수).
