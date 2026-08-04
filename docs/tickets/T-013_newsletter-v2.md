# T-013 뉴스레터 개편 v2 — 파일럿 수신자 피드백 반영

Type: FEAT
Status: TODO (2026-08-01 — 파일럿 수신자 실피드백 6건에서 도출, 민겸 확정)

## Problem

- 현재 동작: 푸디픽은 **아뮤즈부슈(숫자) + 에피타이저 3 + 메인 2** 구성이고 국내3:해외2로 조립된다.
  푸터에 "이 메일에 답장하시면 운영진이 직접 읽습니다"라고 적혀 있다.
- 기대 동작: **에피타이저 2 + 메인 3 + 디저트(원클릭 반응)** 구성, **국내4:해외1**,
  상단에 "오늘의 분야" 한 줄, 답장이 실제로 사람에게 도달한다.
- 왜 필요한가: 파일럿 수신자 피드백 6건 중 4건이 여기에 해당한다.
  ① 아뮤즈 빼고 에피2·메인3·디저트 ② 10대 분류 표시가 좋았다 ④ 국내 기사 위주
  ⑥ 답장을 지메일로 받고 싶다.

  **답장 건은 요청이 아니라 버그다.** `dig MX news.foodtech-center.org` / `dig MX foodtech-center.org`
  둘 다 빈 응답 = 수신함 없음이고, `email_client.send_email`의 Resend payload에 `reply_to`가 없다.
  즉 지금 답장하면 반송된다 — 푸터 문구가 지키지 못할 약속을 하고 있다.

  구조 변경은 큐레이션 뉴스레터의 표준(리드 스토리 + 큐레이션 묶음 + 단일 CTA, 통상 "주제 3 / 링크 2 /
  CTA 1")과도 일치한다. 지금은 반대로(깊은 것 2, 가벼운 것 3) 가고 있었다.

## Context

관련 파일·함수:

- `app/services/newsletter_template.py` — `render_foodie_pick`(코너 조립), `render_text_fallback`,
  `_course_header`/`_headline_item`/`_main_card`, `CATEGORY_LABELS_KO`(10대 분야 한글명), 팔레트 상수.
- `app/services/pilot_daily.py` — `N_DOMESTIC=3`/`N_OVERSEAS=2`, `select_picks`(회전+분야 distinct),
  `build_pilot_daily`(amuse_big/amuse_caption 생성, `PILOT_BANNER` 삽입), `_BANNER_ANCHOR`.
- `app/services/newsletter.py` — `MIN_ITEMS=5`, `build_newsletter`(비파일럿 경로도 같은 렌더러 사용),
  `send_newsletter`(수신자별 `UNSUB_PLACEHOLDER` 치환 후 `send_email` 호출).
- `app/lib/email_client.py` — `send_email` payload 조립 지점(여기에 `reply_to` 추가).
- `app/config.py` — `Settings`(신규 키 추가 지점), `.env.example` 동반 갱신 필요(C6).
- `app/models/engagement_event.py` — `event_type`은 자유 문자열, `payload`는 JSONB.
  **반응 버튼은 이 둘로 적재 가능 → 스키마 변경 불필요.**
- `app/routes/webhooks.py` — 공개 라우트 패턴 참고(반응 수집 엔드포인트도 공개 GET이어야 함).

디자인 시안(스크린샷 검수 완료, 선택 대기): A 에디토리얼 / B 브리핑 / C 카드.
선택된 안을 `docs/branding/newsletter-v2.html`로 커밋하고 렌더러를 거기 맞춘다.

헤더 배너: `docs/branding/foodie-pick-header-1200x320.png` (Canva 생성 → 3.75:1 크롭, 94KB).
표시 폭 600px 기준 높이 160px. 왼쪽 절반이 비어 있으므로 워드마크·부제는 **이미지에 굽지 말고
텍스트로 얹는다**(이미지 차단·접근성). 구현 시 앱에서 서빙할 정적 경로로 옮길 것.

## Scope

허용:

- `app/services/newsletter_template.py` — 코너 재구성(에피2·메인3·디저트), "오늘의 분야" 줄,
  아뮤즈부슈 제거, 선택 시안의 시각 언어 반영, 모바일 대응(고정 600px → 유동 폭).
- `app/services/pilot_daily.py` — `N_DOMESTIC`/`N_OVERSEAS` 4:1, `select_picks` 반환 순서 조정,
  amuse 관련 인자 제거, 반응 링크 주입.
- `app/services/newsletter.py` — `build_newsletter`의 mains/headlines 개수를 새 구성에 맞춤.
- `app/lib/email_client.py` — `reply_to` 지원.
- `app/config.py` + `.env.example` — `newsletter_reply_to` 추가.
- `app/routes/` 신규 반응 수집 라우트 + 서비스 함수(`engagement_events`에 event_type="reacted" 적재).
- `docs/branding/newsletter-v2.html` 신규(선택 시안), `tests/` 해당 테스트.

금지:

- DB 스키마 변경 — 반응은 기존 `engagement_events`(event_type + payload)로 적재한다.
- 기사 링크 URL 변형 — 원본 그대로 유지(T-003 클릭 매칭 전제). 중간 착지 페이지는 T-016 소관.
- 발송 멱등·100명 가드·`provider_id` 저장 로직 변경(T-008 자산 그대로 재사용).
- 관리자 개수 조정 UI — T-014 소관. 이 티켓에서는 상수/기본값까지만.
- 회원 PII를 로그·레포에 남기기(C6), archive/ 수정(C5), Supabase 특화 기능(C3).

## Acceptance Criteria

1. `send_email`이 `reply_to`를 Resend payload에 실어 보내고, 값은 `settings.newsletter_reply_to`에서
   온다. 값이 비어 있으면 헤더를 생략한다(기존 동작 유지). `.env.example`에 키와 용도 주석 추가.
2. 실발송 1통에서 수신자가 "답장"을 눌렀을 때 지정된 지메일 주소가 수신란에 뜬다(라이브 검증).
3. 푸터 답장 문구가 실제 동작과 일치한다(1·2 충족 후에도 참인 문장으로).
4. 렌더 결과가 **에피타이저 2 → 메인 3 → 디저트** 순서이고 아뮤즈부슈 블록이 없다.
5. 헤더 아래 "오늘의 분야" 줄에 그 편에 실린 기사들의 10대 분야 한글명이 표시된다.
6. `select_picks`가 국내 4 · 해외 1로 고르고, 분야 distinct와 일별 회전은 그대로 동작한다.
   꼭지가 부족하면 기존대로 발송하지 않고 실패 신호를 남긴다.
7. 디저트의 반응 버튼 3개(좋았어요/보통/별로)가 각각 공개 URL을 갖고, 클릭 시
   `engagement_events`에 `event_type="reacted"` + `payload`에 반응값·newsletter_id가 적재된다.
   같은 회원이 같은 편에 여러 번 눌러도 마지막 값 1건으로 수렴한다(멱등).
8. 반응 링크는 인증 없이 열려야 하므로 회원 식별자는 추측 불가능한 토큰을 쓴다
   (수신거부 토큰과 같은 등급 — 열거로 남의 반응을 조작할 수 없어야 한다).
9. 텍스트 폴백(`render_text_fallback`)도 새 구성에 맞춰 갱신된다.
10. 모바일 폭(390px)에서 가로 잘림 없이 읽힌다 — 헤드리스 크롬 스크린샷으로 검수.
11. 기존 기능이 깨지지 않는다 — `bash scripts/check.sh` 그린, 기존 발송·추적 경로 무변경.

## Verification

1. `bash scripts/check.sh` — ruff + pyright + pytest 그린 (exit 코드 명시 확인).
2. 렌더 스냅샷: 샘플 아이템 5건으로 `render_foodie_pick` 호출 → HTML 저장 →
   헤드리스 크롬으로 640px·390px 캡처 → 직접 보고 구조(에피2·메인3·디저트)·분야 줄·잘림 확인.
3. `select_picks` 단위 테스트: 국내4:해외1, 분야 distinct, 연속 2일 회전이 다른 집합을 내는지.
4. 반응 엔드포인트: 토큰으로 3개 반응을 순서대로 호출 → `engagement_events`에 1건으로 수렴하는지
   (멱등), 잘못된 토큰은 거부되는지.
5. 라이브: 스테이징 성격으로 본인 주소 1통 실발송 → 실제 메일에서 ① 답장 주소 ② 구조 ③ 분야 줄
   ④ 반응 버튼 클릭 후 DB 적재를 순서대로 확인.
