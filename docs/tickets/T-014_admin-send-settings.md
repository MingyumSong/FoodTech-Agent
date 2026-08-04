# T-014 관리자 발송 설정 — 뉴스 개수·국내외 비율 조정

Type: FEAT
Status: DONE (2026-08-04 — AC 7/7 충족, check.sh 그린 126개.
  app_settings(RLS·왕복 검증) + send_settings(검증·기본값 폴백) + build_pilot_daily 배선 +
  발송검토 탭 설정 폼. 관리자 화면 스크린샷 검수 완료.)

## Problem

- 현재 동작: 한 편에 실리는 꼭지 수와 국내/해외 비율이 코드 상수다
  (`pilot_daily.N_DOMESTIC`/`N_OVERSEAS`, `newsletter.MIN_ITEMS`). 바꾸려면 배포해야 한다.
- 기대 동작: 관리자가 화면에서 **에피타이저 수 / 메인 수 / 국내·해외 비율 / 최근 며칠**을 바꾸면
  다음 발송부터 반영된다.
- 왜 필요한가: 피드백 ⑤ "뉴스 개수를 관리자가 변경할 수 있게". 파일럿 단계라 적정 개수를
  찾는 실험이 계속 필요한데, 매번 배포로 돌리면 실험 주기가 배포 주기에 묶인다.

## Context

관련 파일·함수:

- `app/services/pilot_daily.py` — `N_DOMESTIC=3`/`N_OVERSEAS=2`(T-013에서 4:1로 바뀜),
  `DEFAULT_DAYS=7`, `select_picks(pool, day_index)`, `build_pilot_daily(session, client, days)`.
- `app/services/newsletter.py` — `MIN_ITEMS`(조립 최소 꼭지 수 가드).
- `app/services/admin_pages.py` — 탭 구조 `_TABS`, `_shell`/`_nav`, 폼 스타일 상수(`_FIELD`/`_BTN`/`_CARD`),
  `collect_review`/`render_review_page`(발송 검토 탭 — 설정 폼을 붙일 유력 위치).
- `app/routes/admin.py` — `require_admin_basic` 의존성, POST 후 리다이렉트 패턴(회원 추가/삭제 참고).
- `.claude/rules/alembic-migrations.md` — 새 테이블에는 RLS 활성화를 같은 리비전에 넣을 것(C2).

설계 메모: 설정은 key/value 한 행짜리 테이블(`app_settings`, JSONB value)로 두고 서비스가
`get_send_settings(session)`으로 읽되 **행이 없으면 코드 기본값**을 쓴다 — 마이그레이션 직후에도
발송이 멈추지 않아야 한다.

## Scope

허용:

- `app/models/app_setting.py` 신규 + Alembic 리비전(테이블 생성 + `ENABLE ROW LEVEL SECURITY`).
- `app/models/__init__.py`에 임포트 추가(autogenerate 감지용).
- `app/services/` 설정 읽기/쓰기 서비스 + `pilot_daily`가 상수 대신 이걸 읽도록 변경.
- `app/services/admin_pages.py` 발송 검토 탭에 설정 폼, `app/routes/admin.py`에 POST 핸들러.
- `tests/` 해당 테스트.

금지:

- 발송 상한(`PILOT_MAX_RECIPIENTS=100`)을 화면에서 조정 가능하게 만들기 — 결정 4의 안전장치다.
  코드 상수로 남긴다.
- 뉴스 수집 파라미터(`MAX_DOMESTIC`/`MAX_OVERSEAS`, 검색어)까지 UI로 빼기 — 이 티켓은 **발송 조립**만.
- T-013의 코너 구조 자체를 화면에서 바꾸게 하기(코너 추가/삭제 X — 개수만).
- archive/ 수정(C5), Supabase 특화 기능(C3).

## Acceptance Criteria

1. `app_settings` 테이블이 Alembic 리비전으로 생성되고 RLS가 활성화된다. upgrade/downgrade 왕복 통과.
2. 설정 행이 없으면 코드 기본값으로 동작한다(마이그레이션 직후 발송이 깨지지 않는다).
3. 관리자 화면에서 에피타이저 수·메인 수·국내/해외 비율·최근 일수를 저장하면 값이 유지된다.
4. 저장된 값이 다음 `build_pilot_daily` 조립에 실제로 반영된다.
5. 범위 밖 값(0 이하, 과도하게 큰 수, 국내+해외 ≠ 총 꼭지 수)은 저장 단계에서 거부하고
   사용자에게 이유를 보여준다.
6. 꼭지 수를 늘렸는데 게이트 통과분이 모자라면 기존대로 발송하지 않고 실패 신호를 남긴다.
7. 기존 기능이 깨지지 않는다 — `bash scripts/check.sh` 그린.

## Verification

1. `uv run alembic upgrade head` → `downgrade -1` → `upgrade head` 왕복, Supabase에서 `rowsecurity=true` 확인.
2. `bash scripts/check.sh` 그린 (exit 코드 명시 확인).
3. 관리자 화면에서 메인 3→4로 저장 → 발송 검토 탭에서 오늘 편 재조립 → 미리보기에 메인 4건 확인.
4. 잘못된 값(메인 0, 국내+해외 불일치) 저장 시도 → 거부 메시지 확인.
