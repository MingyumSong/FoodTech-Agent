# T-025 수신거부 — 오클릭 방지(확인 단계) + 되돌리기 경로

Type: BUG
Status: DONE (2026-08-09) — 단 AC 검증 3(운영 실메일 클릭)은 다음 발송 후 확인

## Problem

- **현재 동작:**
  1. 푸터의 수신거부 링크는 **GET을 받는 즉시 구독을 끊는다**(`unsubscribe_get` → `_unsubscribe`).
     확인 단계가 없어 오클릭·메일앱 링크 프리페치도 같은 결과를 낸다.
     (모듈 독스트링은 "GET: 확인 페이지"라고 적혀 있었다 — 문서와 코드가 달랐다.)
  2. 한 번 끊기면 **되돌릴 방법이 코드에 없다.** 완료 화면은 "푸드테크센터로 연락해주세요"라고
     안내하는데, 연락을 받아도 직원이 누를 버튼이 없다. DB를 직접 쓰는 수밖에 없었다.
  3. `subscribed`를 바꿔도 `updated_at`이 갱신되지 않아 **언제 끊겼는지 알 수 없다.**
     실제로 회원 3995의 `updated_at`(2026-07-18)을 수신거부 시각으로 잘못 읽었다가,
     이벤트 이력(08-06까지 수신)으로 반박되고서야 알았다.
- **기대 동작:** GET은 아무것도 바꾸지 않고 확인 페이지만 띄운다. 실제 해지는 POST에서만.
  관리자 회원관리 탭에서 구독 상태를 되돌릴 수 있다. 상태가 바뀌면 `updated_at`이 남는다.
- **왜 필요한가:** 파일럿 25명 중 **이미 1명이 이탈**했고(회원 3995 — 'bad' 반응 43분 뒤 마지막
  클릭, 이후 수신 0), 그게 의도인지 오클릭인지 **구분할 근거가 지금 없다.**
  3,000명 본 발송에서 같은 실수는 되돌릴 수 없는 손실이 된다.

**RFC 8058 one-click은 그대로 유지된다** — Gmail이 부르는 건 `List-Unsubscribe-Post` 헤더에 따른
POST이고, 확인 페이지의 폼도 같은 POST 엔드포인트를 친다. 봇 프리페치는 GET만 하므로 이 분리가
정확히 오탐만 걸러낸다.

## Context

- `app/routes/unsubscribe.py` — `unsubscribe_get`(41행, 부작용 있음) / `unsubscribe_post` / `_unsubscribe`
- `app/services/members.py` — 회원 서비스. 구독 상태 변경 함수를 여기 둔다(라우트에 로직 금지).
- `app/services/admin_pages.py` — `_member_row`(197) 구독 컬럼이 ✅/🚫 표시만 하고 있다.
- `app/routes/admin.py` — `admin_members_delete`(113)가 POST 액션의 기존 패턴.
- `app/services/newsletter.py:162` — `_recipients`가 `subscribed == True`로 거른다. 되살리면 즉시 재수신.

## Scope

허용:

- `app/routes/unsubscribe.py`, `app/services/members.py`, `app/routes/admin.py`,
  `app/services/admin_pages.py`, `tests/test_unsubscribe.py`, `tests/test_admin_pages.py`

금지:

- DB 스키마 변경 (기존 `subscribed`·`updated_at` 컬럼만 쓴다)
- **수신거부한 회원을 코드·스크립트로 일괄 되살리기** — 되살리기는 본인 요청을 받은
  관리자의 개별 조작으로만 일어나야 한다(수신동의)
- 무관한 리팩터링

## Acceptance Criteria

1. `GET /unsubscribe/{token}` 은 `subscribed`를 바꾸지 않고 확인 페이지를 반환한다.
2. 확인 페이지의 "수신거부하기" 버튼은 같은 토큰으로 POST하고, 그때 해지된다.
3. `POST /unsubscribe/{token}` (RFC 8058 one-click 포함) 은 기존대로 즉시 해지·멱등.
4. 없는 토큰은 GET·POST 모두 404.
5. 관리자 회원관리 탭에서 구독 상태를 되돌릴 수 있고, 되살리기는 확인 대화상자를 거친다.
6. 구독 상태가 실제로 바뀐 경우에만 `updated_at`이 갱신된다.
7. 기존 기능이 깨지지 않는다.

## Verification

1. `bash scripts/check.sh` 통과.
2. 로컬에서 토큰으로 `curl` GET → DB `subscribed` 불변 확인, 이어서 POST → `false` 확인.
3. 배포 후 운영에서 실제 발송 메일의 푸터 링크를 눌러 확인 페이지가 뜨는지 본다
   (누르는 것만으로 해지되지 않아야 한다).
4. 회원관리 탭에서 회원 3995의 상태 버튼이 보이는지 확인한다. **누르지 않는다** — 본인 요청 전이다.
