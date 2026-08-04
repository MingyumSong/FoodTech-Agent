# T-018 뉴스 매체명 복원

Type: BUG
Status: DONE (2026-08-04 — 구현·배포·운영 백필 완료. check.sh 그린 148개.
  ⚠️ 티켓 파일이 작업 뒤에 만들어졌다 — 코드 주석·커밋이 먼저 "T-018"을 참조했다. 순서가 거꾸로였다.)

## Problem

- 현재 동작(수정 전): `news_items` **460건 전부** `source`가 빈 문자열이었다. 뉴스레터 메타 줄이
  "KR · 조선비즈"가 아니라 **"KR"로만** 나갔다.
- 기대 동작: 기사마다 매체명이 표시된다.
- 왜 필요한가: 출처 없는 기사 목록은 신뢰도가 떨어진다. T-009 큐레이션의 "소스 신뢰도" 기준도
  이 값이 있어야 만들 수 있고, T-016 착지 페이지는 출처를 크게 보여주는 화면이라 더 도드라진다.

**버그가 아니라 처음부터 채운 적이 없다.** `fetch_naver`/`fetch_brave`가 `"source": ""`를
하드코딩했고(수정 전 `news.py:139`·`183`), 실제 매체명이 들어가는 건 RSS 경로(`_entry_to_item`)뿐인데
T-013에서 네이버·Brave를 국내·해외 1차로 확대하면서 RSS가 폴백으로 밀려났다. 그래서 아무도 몰랐다.

발견 계기는 T-016 착지 페이지 시안에 **실제 수집 데이터를 넣어본 것**이다. 목업에 가짜 데이터를
썼다면 못 봤다.

## Context

- `app/services/news.py` — `fetch_naver`, `fetch_brave`(매체명 필드가 응답에 없다), `_entry_to_item`(RSS).
- `app/services/news_sources.py` — `SOURCE_BY_DOMAIN`, `source_from_url`, `_STRIP_PREFIXES`.
- `app/services/newsletter_template.py` — `_source_line`(source 없으면 region만 표시).
- `scripts/backfill_source.py` — 기존 행 백필(dry_run 기본).

## Scope

허용: `news_sources.py`(매핑·복원 함수), `news.py`(수집기 2곳 연결), 백필 스크립트, 테스트.

금지:

- 매체명을 **추측해서 넣기**. 확실하지 않으면 도메인 폴백에 맡긴다.
- 본문 스크래핑으로 매체명 얻기(결정 2 — 입력은 제목+요약 300자).
- 이미 `source`가 있는 행 덮어쓰기.

## Acceptance Criteria

1. 네이버·Brave 수집분에 매체명이 들어간다 — API에 필드가 없으므로 URL 호스트에서 복원한다.
2. 매핑에 없는 매체는 **도메인을 그대로** 돌려준다. 빈칸보다 낫고 틀린 이름보다 훨씬 낫다.
3. 서브도메인이 다른 매체면 다르게 잡는다(`biz.chosun.com` 조선비즈 ≠ `chosun.com` 조선일보) —
   전체 호스트 → 접두사 제거 → 상위 도메인 순으로 찾는다.
4. 빈 URL·깨진 URL에서 예외 없이 동작한다.
5. 기존 행 백필은 dry_run이 기본이고, 미리보기로 무엇이 어떻게 바뀌는지 볼 수 있다.
6. 기존 기능이 깨지지 않는다.

## Verification

1. `bash scripts/check.sh` — exit=0, 148개 통과(신규 8개). ✅
2. 백필 dry_run → `--apply` → 빈 행 0건 확인. ✅
   운영 실적: 460건 중 매핑 120건(34곳) / 도메인 폴백 340건(274곳) / 실패 0건.
3. 배포 후 다음 발송에서 메타 줄이 "KR · 연합뉴스"로 나오는지. **← 2026-08-05 13:00 발송분에서 확인**

## 남은 것

- 자주 등장하는 폴백 도메인을 매핑에 추가(`yeongnam.com`·`kdfnews.com` 등 실측에서 반복됨).
- 폴백 목록에서 **비뉴스 도메인이 드러났다**(`frontiersin.org` 학술 출판사, `bentosushi.com` 초밥 체인).
  수집 품질 문제라 T-009에서 다룬다.
