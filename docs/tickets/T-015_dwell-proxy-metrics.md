# T-015 체류 근사 지표 — 연속 클릭 간격

Type: FEAT
Status: TODO (2026-08-01 — 파일럿 수신자 피드백 ③에서 도출)

## Problem

- 현재 동작: 참여 지표는 열람 수·클릭 수·분야별 클릭 수뿐이다(`pilot_members` 롤업).
  "얼마나 관심 있게 봤는가"를 나타내는 신호가 없다.
- 기대 동작: 회원이 기사에 **얼마나 시간을 들였는지**의 근사치를 지표로 갖는다.
- 왜 필요한가: 피드백 ③ "체류 시간을 알면 좋겠다".

  **원문 기사 페이지의 실제 체류 시간은 측정할 수 없다** — 그 페이지는 언론사 서버에서 뜨고
  우리 코드를 심을 수 없다. 우리에게 오는 신호는 "링크를 눌러 떠났다"까지다.

  대신 **연속 클릭 간격**을 쓴다: 같은 회원이 기사 A를 누르고 기사 B를 누르기까지의 간격은
  대체로 A를 보고 있던 시간이다. 검색엔진이 랭킹에 쓰는 long click / short click 신호와 같은 원리.
  이미 `engagement_events`에 `member_id`·`url`·`occurred_at`이 다 있어 **추가 수집 없이 계산된다.**

  한계를 지표 자체에 못 박아 둘 것: ① 그 편에서 **마지막으로 누른 기사는 잴 수 없다**(다음 클릭이
  없으므로) → 표본이 전체 클릭의 일부로 줄어든다. ② 간격에는 메일로 돌아와 다음 걸 찾는 시간이
  섞인다. ③ 상한을 두지 않으면 "다음날 다시 열어 클릭"이 몇 시간짜리 체류로 잡힌다.
  → 결정 5와 같은 태도로, **정밀 지표가 아니라 상대적 순위 도구**로 다룬다.

## Context

관련 파일·함수:

- `app/models/engagement_event.py` — `member_id`, `newsletter_id`, `event_type`, `url`, `occurred_at`,
  인덱스 `ix_engagement_events_member_occurred`(member_id, occurred_at) — 이 지표 계산에 그대로 맞는다.
- `app/services/pilot_daily.py` — `refresh_pilot_stats`(send_logs·engagement_events → `pilot_members`
  멱등 롤업, `category_clicks` 계산 패턴이 그대로 참고가 된다).
- `app/models/pilot_member.py` — 집계 컬럼들 + Activity Score용 컬럼(아직 미사용).
- `app/services/admin_pages.py` — `collect_popular`/`render_popular_page`(집계 표시 패턴),
  `_bar_rows`(admin_status에서 재사용 중).
- `docs/tickets/T-016_article-landing-page.md` — 진짜 체류를 재는 후속안(중간 착지 페이지).

## Scope

허용:

- `app/services/` 지표 계산 서비스 신규(회원별·기사별 클릭 간격 집계).
- `refresh_pilot_stats`에서 계산 결과를 롤업(기존 컬럼 활용 범위 내).
- `app/services/admin_pages.py`에 표시(인기 분야 탭 확장 또는 신규 탭).
- `tests/` 해당 테스트.

금지:

- DB 스키마 변경 — 기존 `engagement_events`/`pilot_members` 컬럼으로 해결한다.
  (컬럼이 정말 모자라면 이 티켓을 멈추고 스코프를 다시 합의한다.)
- 기사 링크 URL 변형·중간 착지 페이지 도입 — T-016 소관.
- Activity Score 가중치 확정 — 별도 작업. 이 티켓은 **입력 지표를 만드는 데까지**.
- 회원 PII를 로그에 남기기(C6).

## Acceptance Criteria

1. 회원별로 "연속 클릭 간격"이 계산된다 — 같은 회원의 클릭을 시각 순으로 늘어놓고 인접 간격을 취한다.
2. 간격에 **상한**이 있어(예: 일정 시간 초과분은 제외) 다음날 재열람이 체류로 잡히지 않는다.
   상한값과 근거를 코드 주석에 남긴다.
3. 각 편의 **마지막 클릭은 집계에서 제외**되고, 그 사실이 화면에 드러난다
   (예: "클릭 N건 중 M건 측정 가능") — 표본이 줄어든 걸 숨기지 않는다.
4. 짧은 간격(튕김)과 긴 간격(정독)이 구분 가능한 형태로 노출된다.
5. 관리자 화면에서 이 지표를 볼 수 있고 PII는 표시하지 않는다.
6. 클릭이 1건뿐이거나 0건인 회원에서 예외 없이 동작한다(빈 데이터 안전).
7. 기존 기능이 깨지지 않는다 — `bash scripts/check.sh` 그린, `refresh_pilot_stats` 멱등 유지.

## Verification

1. `bash scripts/check.sh` 그린 (exit 코드 명시 확인).
2. 단위 테스트: 클릭 0건 / 1건 / 3건(정상) / 간격이 상한을 넘는 경우 각각의 기대값.
3. 운영 데이터로 계산해 실제 분포를 확인 — 값이 전부 0이거나 전부 상한이면 상한값을 재검토한다.
4. 관리자 화면 스크린샷 검수(측정 가능 표본 수가 보이는지 포함).
