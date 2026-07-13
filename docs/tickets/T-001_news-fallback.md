# T-001 뉴스 수집 안정화 — 폴백 + 재시도 + 헬스체크 (신규 구현)

Type: TASK
Status: DONE (2026-07-13 — AC 4/4 충족. 라이브 검증: 실키 기준선 80건(naver+brave),
잘못된 Brave 키 → overseas=rss 폴백, 키 전무 → 양쪽 rss 80건, 헬스체크 corrupt/missing 신호 확인.
pytest 27개 통과, ruff·pyright 클린. 구현: app/lib/http.py(백오프 재시도),
app/services/news_sources.py(공용 쿼리·피드 레지스트리), app/services/news.py(폴백 오케스트레이터+캐시+헬스체크),
POST /jobs/news-refresh, GET /health/news)

## Problem

- 배경: 코드는 새로 만든다. `archive/foodtech-hub-deploy/`는 참고용 프로토타입이며,
  거기서 확인된 결함을 신규 구현에서 반복하지 않는 것이 이 티켓의 목적이다.
- 프로토타입의 결함 (반면교사):
  1. `refresh_news_cache()`가 `if BRAVE_API_KEY:` 분기로 소스를 선택 → 키가 **존재하면**
     Brave 호출이 실패해도(한도초과 429, 타임아웃 → `call_brave_search()`가 빈 리스트 반환)
     RSS 폴백으로 넘어가지 않고 빈/부실 캐시가 생성됨.
  2. 재시도·백오프 없음.
  3. 발송 전 뉴스 캐시 상태(신선도·건수)를 점검하는 수단 없음.
- 기대 동작: 신규 뉴스 수집 모듈은 "Brave 실패/0건 → RSS 폴백", "일시 오류 백오프 재시도",
  "발송 전 헬스체크"를 처음부터 갖춘다.
- 왜 필요한가: 주 1회 뉴스레터의 콘텐츠 소스라 수집 실패 = 빈 뉴스레터 발송 사고로 직결.
  Brave 무료 한도(월 2k 요청)상 한도초과는 현실적으로 발생한다.

## Context

참고 코드 (모두 `archive/foodtech-hub-deploy/app.py` — 읽기 전용, 수정 금지):

- `call_brave_search()` (약 L415) — 실패 시 빈 리스트 반환, 호출부가 "실패"와 "0건"을 구분 못 함
- `call_rss_fallback()` (약 L448) — Google News RSS, 키 불필요. 쿼리 목록을 자체 하드코딩
  (Brave 경로의 `NEWS_QUERIES`와 카테고리 체계가 달랐음 → 신규 구현에선 쿼리 목록을 공유할 것)
- `refresh_news_cache()` (약 L477) — 캐시 JSON 구조(`updated_at`, `count`, `source`, `items`)는 재사용 가치 있음
- 소스 분류(`classify_source`)·중복 제거·정렬 로직도 참고 가능

신규 코드 위치: 미정 — 프로젝트 스캐폴딩 시 결정. 이 티켓은 스캐폴딩 이후 착수한다.

## Scope

허용:

- 신규 코드베이스에 뉴스 수집 모듈 작성 (Brave + RSS + 캐시)
- 헬스체크 함수/엔드포인트 추가 (캐시 age·count 검사)

금지:

- `archive/` 내 파일 수정 (참고 전용)
- 발송(캠페인)·이메일 로직 구현 (별도 티켓)
- DB 스키마 작업 (별도 티켓)

## Acceptance Criteria

1. `BRAVE_API_KEY`가 있어도 Brave가 오류/0건이면 RSS 폴백이 동작한다.
2. 일시적 오류(429, 5xx, 타임아웃)에 백오프 재시도가 있다(횟수 제한).
3. 캐시 신선도·건수를 확인하는 헬스체크가 있고, 기준 미달 시 구분 가능한 신호를 준다.
4. Brave 경로와 RSS 경로가 동일한 쿼리/카테고리 목록을 공유한다.

## Verification

1. 앱 실행, 뉴스 API 정상 응답 확인 (기준선).
2. `BRAVE_API_KEY`에 일부러 잘못된 값을 넣고 재실행 → 캐시 `source`가 `rss`로 폴백되고 items가 채워지는지 확인.
3. 키를 아예 비운 경우도 RSS로 동작하는지 확인.
4. 헬스체크 호출 → 정상 캐시에서 OK, 캐시 파일 삭제/오염 상태에서 실패 신호 확인.
