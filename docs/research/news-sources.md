# 뉴스 수집 소스 리서치 — API/RSS 전수 조사

- 조사일: 2026-07-12 (병렬 리서치 에이전트 3개: 국내 / 해외 / 학술)
- 전제: HTML 스크래핑 제외, 공식 API·RSS만 (CLAUDE.md 결정 2)
- 검증: RSS는 실제 fetch로 생존 확인(✅=2026-07-12 HTTP 200 + 유효 XML), API 한도는 공식 pricing/docs 근거

---

## ⚠️ 아키텍처에 영향을 주는 발견 3가지

1. **Brave Search API 무료 티어 폐지 (2026-02).** 전 플랜 종량제 + 월 $5 무료 크레딧(≈1,000 req).
   카드 등록 필수 + 프로젝트 페이지에 attribution 표기 조건. 24h 크론이면 크레딧 내 충분하지만
   "키만 있으면 무료" 전제가 깨짐 → **T-001의 RSS 폴백이 비용 안전장치 역할까지 겸하게 됨**.
   출처: https://api-dashboard.search.brave.com/documentation/pricing
2. **Google News RSS의 링크가 원문 URL이 아님 (2024~).** item link가 `news.google.com/rss/articles/...`
   인코딩 리다이렉트 URL. 뉴스레터에 원문 링크를 실으려면 디코딩 필요하고, 대량 디코딩은 429 사례 多.
   **Resend click 웹훅의 URL 매칭(뉴스별 집계)에도 영향** — Google News 경유 기사는 클릭 URL이
   news.google.com으로 잡힘.
3. **빅카인즈 Open API 2025년부터 유료화**, 카카오는 뉴스 검색 카테고리 자체가 없음 → 둘 다 제외.

---

## 1. 국내 뉴스

### 네이버 뉴스 검색 API — 국내 1차 소스 (추천 ★)

| 항목 | 내용 |
|---|---|
| 엔드포인트 | `https://openapi.naver.com/v1/search/news.json` |
| 인증 | 개발자센터 앱 등록 → `X-Naver-Client-Id/Secret` 헤더 |
| 무료 한도 | **일 25,000회** (검색 API 통합 쿼터) |
| 파라미터 | `query`, `display`(≤100), `start`(≤1000), `sort=date` |
| 날짜 필터 | **없음** — `sort=date` + 응답 `pubDate`로 클라이언트 필터링 |
| 원문 링크 | `originallink`(언론사 원문) + `link`(네이버) 둘 다 제공 |
| 리스크 | 약관상 대량 저장·재배포 제한 → 메타데이터(제목·링크·날짜)만 저장, 본문은 원문 유도. 구현 전 약관 원문 확인 |

### 국내 RSS (전부 키 불필요·무료)

| 소스 | 피드 URL | 검증 |
|---|---|---|
| 식품저널 | `http://www.foodnews.co.kr/rss/allArticle.xml` | ✅ |
| 식품음료신문 | `http://www.thinkfood.co.kr/rss/allArticle.xml` | ✅ |
| 푸드투데이 | `https://www.foodtoday.or.kr/data/rss/news.xml` (⚠️ `/rss/allArticle.xml`은 404) | ✅ |
| 헬로티(산업기술·스마트팜) | `https://www.hellot.net/data/rss/news.xml` | ✅ |
| 농민신문 | RSS 실질 미운영 (200이지만 빈 응답) — 네이버 API 키워드로 대체 | ❌ |
| 연합뉴스 경제 | `https://www.yna.co.kr/rss/economy.xml` (전체: `/rss/news.xml`) | ✅ |
| 매일경제 경제 | `https://www.mk.co.kr/rss/30100041/` (섹션 코드 방식) | ✅ |
| 한국경제 경제 | `https://www.hankyung.com/feed/economy` (`/feed/{섹션}` 패턴) | ✅ |
| 조선비즈 | `https://biz.chosun.com/arc/outboundfeeds/rss/?outputType=xml` (구경로 404) | ✅ |
| 조선일보 경제 | `https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml` | ✅ |
| 전자신문 속보 | `http://rss.etnews.com/Section902.xml` (Section 번호별) | ✅ |

- 전문지 RSS는 "전체 최신기사" 피드 → 푸드테크 키워드 필터링은 수집 후 자체 처리.
- 종합지 경제 섹션은 노이즈 큼 → 키워드 후처리 필수.
- 소규모 매체는 개편 시 URL 변경 잦음(푸드투데이·조선비즈 실례) → 피드별 헬스체크·알림 필요(T-001).

### 제외

| 소스 | 사유 |
|---|---|
| 카카오(다음) 검색 API | 뉴스 검색 미지원 (웹문서로 대체 시 노이즈 과다) |
| 빅카인즈(BIG KINDS) | Open API 2025년 유료화 + 신청 심사 절차 |

---

## 2. 해외 뉴스

### 검색 API 비교

| API | 무료 한도 | 지연 | 상업 이용(무료) | 한국어 | 판정 |
|---|---|---|---|---|---|
| **Brave Search** (현 주력) | 월 $5 크레딧 ≈ 1,000 req (무료 티어 폐지) | 없음 | ✅ (attribution 조건) | ✅ | **유지** — 단 카드 등록 + 폴백 필수 |
| **NewsData.io** | 200 크레딧/일 (1크레딧=10건) | 12h | ✅ **무료 플랜도 허용** | 지원 목록에 ko | **추가 후보 ★** — 무료 API 중 유일하게 약관 적합 |
| NewsAPI.org | 100 req/일 | 24h | ❌ production 금지 | ✅ | 제외 (약관 위반) |
| GNews.io | 100 req/일 | 12h | ❌ 비상업 전용 | ✅ | 제외 (약관 위반) |
| Mediastack | 100 req/**월** | 有 | ❌ | ❌ ko 없음 | 제외 |
| Guardian Open API | 500/일, 본문 전체 | 없음 | ❌ Developer 키 비상업 | 영어만 | 보류 (교육기관 성격이면 협의 여지) |
| NYT API | 500/일, 5/분 | 없음 | 비상업 + 크레딧 표기 | 영어만 | 보류 (메타데이터·스니펫만) |

### Google News RSS (현 폴백) — 유지, 단 링크 디코딩 이슈

- 문법: `https://news.google.com/rss/search?q={쿼리}&hl=ko&gl=KR&ceid=KR:ko`
  - 연산자: `"정확구"`, `OR`, `-제외`, `site:`, `intitle:`, `when:7d`, `after:/before:YYYY-MM-DD`
- 한국어 검색 ✅ 동작 확인 (`q=푸드테크` → 국내 기사 정상 반환)
- 리스크: 비공식·무문서 / **item link가 인코딩 리다이렉트 URL**(원문 복원에 디코딩 필요, 대량 시 429) / rate limit 미공표(24h 캐시 + 쿼리당 1회/일이면 실무상 무해)

### 해외 매체 RSS

| 매체 | 피드 URL | 검증 | 비고 |
|---|---|---|---|
| **AgFunder News** | `https://agfundernews.com/feed` | ✅ | agtech·foodtech·투자 — 주제 적합도 최고 |
| **Green Queen** | `https://www.greenqueen.com.hk/feed/` | ✅ | 대체단백질·배양육 특화, 아시아 시각 |
| **Food Dive** | `https://www.fooddive.com/feeds/news/` | ✅ | 미국 식품산업 전반, 갱신 활발 |
| **FoodNavigator** | `https://www.foodnavigator.com/arc/outboundfeeds/rss/` | ✅ | 식품과학·성분 (`/rss`는 404) |
| Just Food | `https://www.just-food.com/feed/` | ✅ | xmlns 중복(경미) — 대부분 파서 OK |
| The Spoon | `https://thespoon.tech/feed/` | ✅ | 갱신 뜸함(주 1~2건) — 보조 |
| TechCrunch foodtech 태그 | `https://techcrunch.com/tag/foodtech/feed/` | ✅ | WordPress — 모든 태그에 `/feed/` 가능. 갱신 뜸함 |
| Food Business News | `https://www.foodbusinessnews.net/rss/articles` | ✅* | **기본 UA 403 — 브라우저 User-Agent 헤더 필수** |
| Food Engineering | — | ❌ | 봇 차단(403, UA 우회 불가) — 제외 |

---

## 3. 학술 (뉴스레터 논문 코너용)

| 소스 | 인증 | 한도 | 초록 | 판정 |
|---|---|---|---|---|
| **OpenAlex** | 무료 키 권장 | ⚠️ 2025~26 요금제 개편: 무료 키 $1/day 크레딧 (주 1회 소량엔 충분) | ✅ inverted index (재조립 코드 필요) | **1차 ★** — search+날짜+topics 필터로 5개 도메인 횡단 |
| CrossRef | 불필요 (`mailto`로 polite pool) | 50 req/s | ❌ 결측 많음 | DOI 메타데이터 보강용 |
| PubMed E-utilities | 키 무료 (10 req/s, 무키 3/s) | 충분 | ✅ 좋음 | 2차 — food safety·발효(미생물) 보강. esearch→efetch 2단계 |
| Semantic Scholar | 키 승인제 | 무키 5,000/5분(전역 공유 → 429 위험) | ✅ | 후순위 |
| arXiv | 불필요 | 3초 간격 | ✅ | **제외** — food science 카테고리 없음 |

### 저널 RSS (전부 ✅ 라이브)

| 저널 | 피드 URL | 비고 |
|---|---|---|
| Nature Food | `https://www.nature.com/natfood.rss` | 초록 일부 포함 |
| npj Science of Food | `https://www.nature.com/npjscifood.rss` | 오픈액세스 |
| Food Chemistry | `https://rss.sciencedirect.com/publication/science/03088146` | ⚠️ 초록 미제공 → DOI로 OpenAlex 보강 |
| Trends in Food Sci & Tech | `https://rss.sciencedirect.com/publication/science/09242244` | 리뷰지 — 뉴스레터 소재 적합 |
| Journal of Food Science | `https://onlinelibrary.wiley.com/feed/17503841/most-recent` | Wiley/IFT |

---

## 4. 종합 권고 — 소스 스택

| 층 | 소스 | 역할 |
|---|---|---|
| 국내 1차 | 네이버 뉴스 API | 키워드 검색 (일 25k 여유) |
| 국내 폴백 | 식품저널·식품음료신문·푸드투데이·헬로티 RSS | 키 불필요 — T-001 폴백 풀 |
| 해외 1차 | Brave Search API | 유지 (월 $5 크레딧 내) |
| 해외 폴백 | AgFunder·Green Queen·Food Dive·FoodNavigator RSS + Google News RSS | Brave 실패/크레딧 소진 시 |
| 해외 보조 API | NewsData.io (검토) | 무료 중 유일한 약관 적합 — 필요 시 추가 |
| 학술 | OpenAlex(1차) + 저널 RSS 3~5종 + PubMed(보강) | 주 1회 논문 5~10건 |

### 구현 시 주의 (기존 결정과의 정합)

- 모든 소스 재시도+백오프, 소스별 헬스체크·알림 → **T-001 범위**
- Google News 링크 디코딩 여부 결정 필요 — 미디코딩 시 클릭 추적(Resend 웹훅) URL 집계가 news.google.com으로 뭉개짐
- Brave: 카드 등록 + attribution 표기 / OpenAlex·CrossRef: `mailto=news@foodtech-center.org` 필수
- Food Business News만 브라우저 UA 헤더 필요
- 수집 로직은 서비스 함수로 분리, `/jobs/*` 규약(C4) 준수
