# UI 수정 지도 — "여기여기 만지면 돼요"

화면에서 눈에 보이는 것을 고치려 할 때 **어느 파일 어느 함수를 열면 되는지**만 적은 문서다.
파일럿 수신자 피드백("수정이 필요할 때 어디를 만지면 되는지 알려달라") 반영.

이 프로젝트엔 별도 템플릿 파일(.html/.jinja)이 거의 없다. **HTML을 파이썬 함수가 문자열로
조립**한다. 그래서 "템플릿 폴더"를 찾으면 안 나오고, 아래 함수들을 찾아야 한다.
(예외: `docs/branding/newsletter-v2.html` 은 **시안**이다 — 여기를 고쳐도 발송 메일은 안 바뀐다.)

고친 뒤에는 항상 `bash scripts/check.sh` 를 돌린다. 그게 CI와 같은 검사다.

---

## 1. 뉴스레터 메일 (수신자가 받는 화면)

전부 `app/services/newsletter_template.py` 한 파일이다.

| 고치고 싶은 것 | 열 곳 |
| --- | --- |
| 색 (네이비·강조색·회색·배경) | 파일 맨 위 상수 `NAVY` `ACCENT` `INK` `GRAY` `LINE` `BG` … |
| 글꼴 | `FONT` / `MONO` |
| 상단 로고·제호·발행호수 줄 | `_header()` |
| 헤더 아래 "오늘의 분야" 한 줄 | `_today_strip()` |
| 코너 이름과 설명 ("에피타이저 / 가볍게 훑는 2") | `render_foodie_pick()` 안의 `_section_label(...)` 호출 3줄 |
| 에피타이저 카드 모양 | `_headline_item()` |
| 메인 카드 모양 (좌측 레일·요약 길이) | `_main_card()` — 요약 자르는 길이는 `summary_limit` |
| 분야 칩(뱃지) 색·모양 | `_chip()` |
| 매체명·지역 표시 줄 | `_source_line()` / `_meta_row()` |
| 반응 버튼 3개의 문구·순서 | `REACTIONS` 상수 (`("good", "👍 좋았어요")` …) |
| 반응 버튼 영역 디자인 | `_dessert()` |
| 맺음말("내일 더 신선한 픽으로…") | `render_foodie_pick()` 아래쪽 문단 |
| 푸터·수신거부 문구 | `render_foodie_pick()` 맨 끝 |
| 분야 한글 이름 | `CATEGORY_LABELS_KO` |
| 메일 제목 형식 (`푸디픽 #018 \| …`) | **여기 아님** → `app/services/pilot_daily.py`의 `subject=` |
| 텍스트 전용 버전 | `render_text_fallback()` |

**주의**

- 헤더 아이콘은 `app/static/foodie-icon.png`. 네이비 `#042A4F`는 이 이미지에서 뽑은 값이라
  **아이콘을 안 바꾸면 색도 바꾸지 않는다** (헤더와 아이콘 배경이 어긋난다).
- 파일럿 배너는 템플릿이 아니라 `pilot_daily.py`가 `_BANNER_ANCHOR` 문자열을 찾아 끼워 넣는다.
  템플릿에서 그 앵커 부분을 지우면 **조립이 예외로 실패한다** (일부러 그렇게 해뒀다 —
  배너가 조용히 사라지는 것보다 낫다).
- 메일 HTML은 웹페이지와 다르다. flex/grid·외부 CSS·`<style>` 선택자가 잘 안 먹는다.
  지금처럼 **인라인 style + table 레이아웃**을 유지할 것.

**바꾸고 나서 눈으로 확인하는 법** (발송하지 않고):

```bash
uv run uvicorn app.main:app --reload
# 브라우저에서 http://localhost:8000/admin/review/preview  (관리자 인증 필요)
```

---

## 2. 관리자 화면 (`admin.foodtech-center.org`)

`app/services/admin_pages.py` (탭 1·2·4·5) + `app/services/admin_status.py` (현황판).

| 고치고 싶은 것 | 열 곳 |
| --- | --- |
| 상단 탭 이름·순서·추가 | `_TABS` 상수 → 새 탭은 `app/routes/admin.py`에 라우트도 함께 |
| 페이지 공통 틀(머리·바탕) | `_shell()` / `_nav()` |
| 버튼·입력칸·카드 스타일 | `_BTN` / `_FIELD` / `_INPUT` / `_CARD` |
| 회원 목록 한 줄 | `_member_row()` |
| 구독 해지·되살리기 버튼 | `_sub_form()` |
| 한 페이지에 몇 명 | `PER_PAGE` |
| 인기 분야 탭 | `render_popular_page()` (숫자는 `collect_popular()`) |
| "읽은 깊이" 카드 | `_dwell_card()` |
| 참여도 탭 화면 | `render_scores_page()` (숫자는 `collect_scores()`) |
| 등급 이름·색 (활발/관심/잠잠) | `TIER_LABELS_KO` / `TIER_CHIP` / `TIER_ORDER` |
| 내려받는 CSV 열 | `CSV_COLUMNS` |
| 발송검토 탭 | `render_review_page()` (숫자는 `collect_review()`) |
| 현황판 | `app/services/admin_status.py`의 `render_status()` |

**규칙**: `collect_*` 는 숫자를 모으고 `render_*` 는 HTML만 만든다. **화면만 고칠 땐
`render_*` 만 열면 된다.** DB 쿼리를 `render_*` 안에 넣지 말 것.

**바꾸고 나서 눈으로 확인하는 법**:

```bash
bash scripts/shot.sh          # 헤드리스 크롬으로 관리자 화면 캡처
```

---

## 3. 수신자가 보는 나머지 페이지

| 화면 | 파일 |
| --- | --- |
| 수신거부 확인 페이지 / 완료 페이지 | `app/routes/unsubscribe.py` — `_CONFIRM_INNER` / `_DONE_INNER` |
| 반응 버튼 누른 뒤 뜨는 페이지 | `app/routes/reactions.py` — `_message()` / `_done_html()` |

이 두 화면은 **로그인 없이 아무나 열 수 있는 유일한 페이지**다. 회원 이름·이메일을
찍지 않는다(C6).

---

## 4. 화면이 아니라 '내용'을 바꾸고 싶을 때

| 바꾸고 싶은 것 | 열 곳 |
| --- | --- |
| 꼭지 수·국내해외 비율·기간 | **코드 말고 관리자 화면** — 발송검토 탭의 설정 폼 |
| 위 설정의 기본값 | `app/services/pilot_daily.py` 상단 `N_DOMESTIC` `N_OVERSEAS` `N_MAINS` … |
| 어떤 기사를 빼는가 (칼럼·광고성 등) | `app/services/news_classify.py`의 `RELEVANCE_GATE_PROMPT` |
| 메인/에피타이저를 가르는 기준 | 같은 프롬프트의 `DEPTH` 절 (1~5 점수) |
| 중복 기사 병합 민감도 | `app/services/curation.py`의 `SIMILARITY_THRESHOLD` |
| 뉴스 수집처 | `app/services/news_sources.py` |
| 매체 이름 표시 | `SOURCE_BY_DOMAIN` (표시용) — 신뢰도 `PREFERRED_SOURCE_DOMAINS`와 **다른 것** |
| 참여 점수 계산 | `app/services/activity_score.py` 상단 상수 한 곳 |
| 발송 시각 | `.github/workflows/`의 크론 |

프롬프트를 고쳤으면 **말로 판단하지 말고 실제 기사로 돌려본다.** 게이트는
`temperature=0`이라 같은 입력이면 같은 결과가 나온다 — 고치기 전후를 비교할 수 있다.

---

## 안 만져야 하는 곳

- `archive/foodtech-hub-deploy/` — 옛 프로토타입. 읽기만 한다.
- `alembic/versions/` 의 **이미 적용된** 마이그레이션 — 새 리비전으로 전진한다.
- `PUBLIC_BASE_URL` — 이미 나간 메일의 수신거부·반응 링크 기준이다. 바꾸면 갈린다.
- `.env`, `uv.lock` — 훅이 수정을 막는다.
