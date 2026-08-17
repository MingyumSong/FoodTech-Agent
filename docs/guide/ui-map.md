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

- 헤더 아이콘은 `app/static/foodie-icon.png`. **배경 없는 투명 PNG(선화)라 헤더 색을 자유롭게
  바꿔도 이음매가 생기지 않는다.** (예전엔 "네이비 `#042A4F`는 아이콘에서 뽑은 값이라 바꾸지 말
  것"이라고 적혀 있었는데, 2026-08-18에 배경 위에 얹어 확인해보니 사실이 아니었다. 다만 선화
  색이 연한 하늘색이라 **밝은 배경 위에 놓으면 거의 안 보인다** — 어두운 헤더가 전제다.)
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

## 1.5 대시보드 (`/admin/dashboard`) — 새로 만드는 쪽 (T-027)

푸드테크 전반을 한 페이지에 담는 화면. **여기는 파이썬이 HTML을 조립하지 않는다** —
브라우저가 JSON API로 데이터를 받아 그린다. 아래 2번(기존 5탭)과 방식이 다르니 헷갈리지 말 것.

| 고치고 싶은 것 | 열 곳 |
| --- | --- |
| 섹션 목록·순서·제목 | `app/static/dashboard/dashboard.js` 의 `SECTIONS` |
| 히어로·푸터 | `app/templates/dashboard.html` |
| 히어로 KPI 카드 내용 | `dashboard.js` 의 `renderHeroStats` (값은 `/admin/api/newsletter` 의 `kpis`) |
| 우리가 만든 컴포넌트 모양 | `dashboard.css` **4부** (알림·빈 자리·페이저·개발배너 등) |
| 색·간격·반경 (디자인 토큰) | ⚠️ 아래 "디자인은 가져온 것이다" 참고 — 함부로 고치지 않는다 |

### 디자인은 가져온 것이다 (고치기 전에 읽을 것)

`dashboard.css` 는 **`HeejeongH/foodtech-dashboard` 의 `index.html` `<style>` 을 그대로 옮긴 것**이고
네 부분으로 나뉘어 있다.

| 부 | 내용 | 손대도 되나 |
| --- | --- | --- |
| 1 | 원본 전역 토큰 (`:root` — `--brand-500`, `--accent-purple`, `--accent-gold` …) | ❌ |
| 2 | 원본 범용 컴포넌트 (`.data-table`, `.form-*`, `.status-*`, `.btn*`) | ❌ |
| 3 | 원본 `.snu-hero-page` 스코프 테마 (**이 화면 디자인의 거의 전부**) | ❌ |
| 4 | 우리가 만든 것 (원본에 짝이 없는 것만) | ✅ |

1~3부의 값을 눈대중으로 고치지 말 것. 한 번 그렇게 다시 지었다가 개별 색은 그럴듯한데
합쳐진 인상이 원본과 완전히 갈라졌다(퍼플·코랄이 빠지고 막대 그라디언트가 단색이 됐다).

원본에는 테마가 **두 겹**이다. 전역 `:root`(1부)와 `.snu-hero-page` 스코프(3부)이고,
**3부가 1부 토큰을 참조하므로 둘 다 있어야 색이 맞는다.** 한쪽만 가져오면 회색으로 떨어진다.
회귀 테스트 `test_dashboard_assets_are_public_and_load` 가 두 겹이 다 실렸는지 본다.

**클래스 이름도 원본을 따른다.** 새 이름을 지으면 원본 `index.html` 과의 대응이 끊겨서
"원본에서 이 모양 찾아 쓰기"가 불가능해진다. 쓸 수 있는 조각:

| 쓰임 | 클래스 |
| --- | --- |
| 판 하나 | `.snu-panel` + `.snu-panel-title` |
| 2열(1.4fr 1fr) 배치 | `.snu-events-layout` |
| KPI 격자 (칸 수에 따라 자동 접힘) | `.snu-stat-grid` + `.snu-stat` |
| 가로 막대 한 줄 | `.snu-hbar-row` (`.lbl` / `.bar > span` / `.n`) |
| 순위 목록 (네이비+골드 강조판) | `.snu-top-presenters` + `.snu-presenter` |
| 표 (가로 스크롤 포함) | `.table-wrap` + `.data-table` |
| 상태 칩 | `.status-pill` + `.status-joined`/`pending`/`none`/`scheduled`/`cancelled` |
| 입력 | `.form-input` / `.form-select` |

**이름이 겹쳐서 조심할 것 둘**

- `.toast` 는 쓰지 않는다. 원본 `.toast` 는 우하단에 떠서 사라지는 `position:fixed` + `.show`
  짜리다. 모달 안에 남는 배너는 **`.alert` + `.alert-ok`/`.alert-bad`** 를 쓴다.
- `.field` 를 입력에 쓰지 않는다. 원본에서 `.snu-popover-body .field` 는 `키:값` 표시 행이라
  모달 안 입력에 붙이면 레이아웃이 뒤집힌다.

`.snu-hbar-row .lbl` 은 **100px 고정**이다. 긴 한글 라벨은 두 줄로 접히니 라벨을 짧게 쓰고
설명은 위 `.t-body` 줄로 옮긴다(읽은 깊이 막대가 그렇게 되어 있다).

**새 섹션을 추가하려면 세 곳만 만지면 된다:**

1. `dashboard.js` 의 `SECTIONS` 에 항목 추가 (`no`, `id`, `title`, `sub`, `owner`)
2. `endpoint` 에 JSON API 주소를 적고, 그 API를 `app/routes/admin.py` 에 만든다
   (계산은 서비스 함수에 두고 라우트는 HTTP만 — 규칙대로)
3. `render(data)` 를 채운다 — 응답을 받아 섹션 본문 HTML 문자열을 만든다

섹션 **본문 밖**(히어로 등)을 채워야 하면 `postRender(data)` 를 쓴다 — 04가 KPI 넷을
히어로 카드로 올리는 데 그걸 쓴다. 실패해도 본문은 이미 떠 있게 되어 있다.

`endpoint` 를 `null` 로 두면 "아직 비어 있음" 자리로 그려진다. 지금 01~03이 그 상태다.

### 처음 시작하는 사람에게

```bash
bash scripts/dev.sh        # Postgres 기동 → 스키마 적용 → 서버 실행
# → http://localhost:8000/admin/dashboard
```

**시크릿(`.env`)이 없어도 화면은 뜹니다 — 단 위 `scripts/dev.sh`로 띄울 때만.**
개발 모드는 `ADMIN_TOKEN`이 비어 있고 `APP_ENV`가 `local`/`dev`/`test`일 때만 켜지는데,
**`APP_ENV` 기본값이 `prod`라** 맨 `uv run uvicorn app.main:app`으로는 잠깁니다
(환경변수를 안 넣은 배포가 곧 무인증 공개였던 적이 있어, 부재를 열림으로 해석하지 않도록
기본값을 뒤집었습니다 — `6f7b05e`). `dev.sh`가 `APP_ENV=local`을 명시해 줍니다.
개발 모드로 뜨면 화면 맨 위에 주황색 배너가 붙습니다.
발송·수집·LLM은 키가 없으면 동작하지 않지만 화면 개발엔 필요 없습니다.

운영은 `APP_ENV=prod`라 절대 열리지 않습니다 — 두 조건이 **모두** 맞아야 하고,
하나라도 어긋나면 잠깁니다(`app/config.py`의 `Settings.dev_mode`).

**규칙 두 가지**

- **셸에 숫자를 박지 않는다.** 계산은 서버가 끝내서 보내고 화면은 그리기만 한다.
  (원본 대시보드가 손으로 적은 값 때문에 실제로 낡아버린 게 이 작업의 출발점이다.
  회귀 테스트 `test_shell_carries_no_data` 가 지킨다.)
- **셸 HTML은 `app/templates/` 에 둔다.** `app/static/` 은 공개 마운트라 거기 두면
  인증이 통째로 우회된다. 이것도 테스트가 지킨다.

### 모달 (상세·조작)

섹션에 `actions: [{ label, run }]` 을 선언하면 머리에 버튼이 붙는다. 상세와 조작은 모달로:

```js
import { openModal, api, toast, withBusy } from "./modal.js";
openModal({ title: "행사 관리", subtitle: "…", render: async () => "<p>…</p>" });
```

- `api(url, {method, body})` — 실패하면 서버가 준 사유를 그대로 던진다. **삼키지 말 것.**
- `withBusy(btn, fn)` — 누른 버튼을 잠근다. **발송·삭제가 두 번 실행되는 걸 막는 유일한 장치.**
- `refresh()` — 데이터가 바뀐 뒤 모달을 다시 그린다.
- 되돌릴 수 없는 조작의 확인 문구엔 **무슨 일이 벌어지는지**를 적는다.
  "정말요?"는 아무것도 알려주지 않는다 — `members-modal.js` 의 `CONFIRM` 참고.
- **가능/불가 판정은 서버가 한다.** 화면이 조건을 따로 들고 있으면 언젠가 어긋나서
  "보낼 수 있다"고 해놓고 서버는 400을 내는 상태가 된다(`review_panel` 의 `can_send` 참고).

## 2. 관리자 화면 (`admin.foodtech-center.org`) — 기존 5탭

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
