# T-012 관리자 페이지 — 회원관리 · 인기분야 · 발송검토

Type: FEAT
Status: DONE

## Problem

- 현재 동작: 관리자 화면이 읽기 전용 현황판(`GET /admin/status`, T-010) 하나뿐. 회원을 손으로
  넣고 빼거나, 어떤 분야가 인기인지 보거나, 발송 전 편을 검토할 화면이 없다.
- 기대 동작: Basic 인증 뒤에 탭형 관리자 페이지 — ① 회원 관리(직접 입력/삭제 + 프로그램·구분 필터),
  ② 이번 주 인기 분야(클릭 집계), ④ 발송 전 최종 검토(오늘 편 미리보기 + 수동 발송).
- 왜 필요한가: 로드맵 항목 4. 운영자가 회원·발송을 눈으로 보고 손볼 도구가 있어야 파일럿을 굴린다.
  (③ 세그먼트별 Activity Score 대시보드는 점수 로직 선행 필요 → 별도 티켓/다음 세션.)

## Context

관련 파일·패턴:
- `app/routes/admin.py`: `require_admin_basic`(Basic admin/ADMIN_TOKEN) — **재사용**. 서버 렌더 HTML.
- `app/services/admin_status.py`: 팔레트 상수(ACCENT 등)·`_bar_rows`·`_card` 렌더 헬퍼 — 재사용/일관.
- `app/services/members.py`: `list_members`(program 필터·페이지네이션)·`create_member`(MemberCreate,
  program/cohort로 member_programs 링크). 삭제 함수는 없음 → 추가.
- `app/models/member.py`: 회원 필드. **기업/개인 구분은 단일 컬럼이 없다** — 로스터 "구분"이
  `Member.category`로 들어옴(member_import). 그래서 필터는 DB 실값 기반 드롭다운으로 만든다.
- `app/services/pilot_daily.py`: `build_pilot_daily`·`_recipients`·`send_newsletter`·
  `refresh_pilot_stats` — 발송 검토 탭에서 재사용.
- `app/services/newsletter_template.py`: `CATEGORY_LABELS_KO`(슬러그→한글) — 분야 라벨.

## Scope

허용:
- `app/services/members.py`에 `delete_member(session, member_id)` 추가.
- `app/services/admin_pages.py` 신규: 탭 1·2·4 데이터 수집 + HTML 렌더 + 공용 탭 내비.
- `app/routes/admin.py`에 라우트 추가:
  - `GET /admin/members`(목록+필터+추가폼), `POST /admin/members`(추가), `POST /admin/members/{id}/delete`.
  - `GET /admin/popular`(인기 분야).
  - `GET /admin/review`(오늘 편 검토), `POST /admin/review/build`(조립), `GET /admin/review/preview`,
    `POST /admin/review/send`(수동 발송).
  - `/admin/status`에 탭 내비 추가.
- `tests/test_admin_pages.py` 신규.

금지:
- DB 스키마 변경(기존 컬럼만 사용).
- 발송 로직(`send_newsletter`) 수정 — 재사용만.
- 회원 PII를 **로그·커밋**에 남기기(화면 표시는 인증 뒤 관리 목적상 허용 — 아래 결정).
- 매직링크 인증 신규 구현(이번 티켓 밖 — 임시 Basic 유지).

## 결정 (이 티켓에서 확정)

- **인증**: 기존 Basic(admin/ADMIN_TOKEN) 재사용. 쓰기(추가·삭제·발송)도 당분간 Basic로.
  매직링크는 후속(archive의 magic_links/admin_sessions 참고).
- **PII 노출**: 회원 관리 탭은 이름·이메일·소속을 표시한다 — 관리 도구라 불가피. 인증 뒤에서만
  노출하고, 로그·커밋엔 남기지 않는다(C6). 현황판(status)의 "집계만" 원칙은 그 페이지에 한한 것.
- **기업/개인 필터**: 전용 컬럼이 없으므로 `Member.category`(로스터 "구분")의 **실제 distinct 값**을
  드롭다운으로 노출한다. 데이터가 기업/개인/기관을 담고 있으면 그대로 필터가 된다.
- **발송 탭 부작용 차단**: GET(검토)에서는 조립·발송을 하지 않는다. 조립·발송은 명시적 POST 버튼으로만
  (LLM 비용·실발송 사고 방지). 크론 자동발송(13:00)과 중복돼도 send_newsletter 멱등이라 안전.

## Acceptance Criteria

1. `GET /admin/members`(Basic): 프로그램·구분 드롭다운 필터 + 이름/이메일 검색 + 페이지네이션으로
   회원 목록을 보여준다. 인증 없으면 401.
2. `POST /admin/members`로 회원을 직접 추가(이름 필수, 이메일·프로그램·구분 선택)하고,
   `POST /admin/members/{id}/delete`로 삭제한다. 삭제는 member_programs 링크도 함께 정리한다.
3. `GET /admin/popular`(Basic): 최근 7일 클릭을 뉴스 분야로 집계해 순위로 보여준다(집계만, PII 없음).
4. `GET /admin/review`(Basic): 오늘의 pilot-daily 편이 있으면 제목·상태·수신자 수·미리보기 링크와
   [지금 발송] 버튼을, 없으면 [오늘 편 조립] 버튼을 보여준다. 조립/발송은 POST에서만 일어난다.
5. `POST /admin/review/send`는 수신자 100 가드를 지나 send_newsletter로 발송하고 통계를 롤업한다.
   이미 sent면 멱등 스킵.
6. 모든 탭에 공용 내비가 있고, 기존 `/admin/status`가 깨지지 않는다.

## Verification

1. `uv run pytest tests/test_admin_pages.py -q` — 인증 게이트(401), 목록·필터, 추가·삭제,
   인기분야 집계, 검토 페이지 상태 분기, 발송 멱등 통과.
2. `bash scripts/check.sh` — ruff + pyright + 전체 pytest 그린.
3. (배포 후) 브라우저로 `/admin/members`·`/admin/popular`·`/admin/review` 열어 눈으로 확인.
