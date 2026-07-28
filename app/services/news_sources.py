"""뉴스 수집 소스 레지스트리.

검색 쿼리는 네이버(국내)·Brave(해외)·Google News RSS(해외 폴백)가 공유한다 (T-001 AC4).
카테고리는 정부 "푸드테크 10대 핵심분야" 체계를 따른다 (CLAUDE.md 결정 2).
피드 URL은 docs/research/news-sources.md에서 2026-07-12 fetch 검증된 것만 싣는다.
"""

from typing import NamedTuple


class SearchQuery(NamedTuple):
    category: str  # 푸드테크 10대 핵심분야 (+ "일반")
    ko: str  # 네이버 뉴스 API용
    en: str  # Brave / Google News RSS(해외)용
    # 니치 검색어는 최신순(date)이 형태소 퍼지 매칭 노이즈로 도배됨 → 관련도순(sim) 병행 수집.
    # 2026-07-21 실측: 식품프린팅 date 1/10 관련 → sim 8/10. 구문검색·제외연산자는 API 미지원.
    naver_sim: bool = False


SEARCH_QUERIES: list[SearchQuery] = [
    # 노이즈 큰 검색어(총보유 1만+)는 최신순만으론 형태소 퍼지 매칭에 도배돼 sim 병행(07-28 실측)
    SearchQuery("일반", "푸드테크", "foodtech", naver_sim=True),
    SearchQuery("세포배양식품", "배양육 OR 세포배양식품", "cultivated meat"),
    SearchQuery("식물기반식품", "대체육 OR 식물성 대체식품", "plant-based food"),
    SearchQuery("간편식", "간편식 OR 밀키트", "ready meal HMR"),
    SearchQuery("식품프린팅", "식품 3D프린팅", "3D food printing", naver_sim=True),
    SearchQuery("스마트제조", "식품 스마트팩토리", "smart food manufacturing", naver_sim=True),
    SearchQuery("스마트유통", "식품 콜드체인 OR 식품 스마트유통", "food cold chain technology"),
    SearchQuery("커스터마이징", "맞춤형 식품 OR 개인맞춤 영양", "personalized nutrition"),
    SearchQuery("외식 푸드테크", "서빙로봇 OR 조리로봇", "restaurant robot automation"),
    SearchQuery("업사이클링", "푸드 업사이클링", "food upcycling", naver_sim=True),
    SearchQuery("친환경포장", "친환경 식품포장", "sustainable food packaging", naver_sim=True),
]

# 국내 전용 확장 검색어 — 네이버만 순회(en=""로 Brave/해외는 안 건드림). 국내 회원 위주라
# 국내 커버리지를 최대화한다: 니치 도메인 동의어 + 일반 푸드테크 저변(2026-07-28 결정, 항목 1).
DOMESTIC_EXTRA_QUERIES: list[SearchQuery] = [
    SearchQuery("일반", "푸드테크 스타트업", "", naver_sim=True),
    SearchQuery("일반", "농식품 벤처 투자", ""),
    SearchQuery("일반", "정밀발효", ""),
    SearchQuery("세포배양식품", "세포농업 OR 배양육 상용화", ""),
    SearchQuery("식물기반식품", "비건 식품 OR 대체 단백질", ""),
    SearchQuery("식물기반식품", "식물성 단백질", "", naver_sim=True),
    SearchQuery("간편식", "가정간편식 HMR", ""),
    SearchQuery("스마트유통", "신선식품 새벽배송 OR 식품 물류 자동화", ""),
    SearchQuery("커스터마이징", "고령친화식품 OR 메디푸드", ""),
    SearchQuery("외식 푸드테크", "무인 매장 로봇 OR 푸드테크 매장", "", naver_sim=True),
    SearchQuery("친환경포장", "생분해 식품포장 OR 친환경 포장재", "", naver_sim=True),
    SearchQuery("스마트제조", "식품 제조 자동화", "", naver_sim=True),
    SearchQuery("식품프린팅", "3D 푸드프린팅", "", naver_sim=True),
]


class RssFeed(NamedTuple):
    name: str
    url: str
    keyword_filter: bool  # 종합 피드 → 푸드테크 키워드 후처리 필요 여부
    headers: dict | None = None  # 일부 매체는 브라우저 UA 필수


# 국내 폴백 풀 — 식품 전문지 (T-001 폴백, 전부 키 불필요)
DOMESTIC_FEEDS: list[RssFeed] = [
    RssFeed("식품저널", "http://www.foodnews.co.kr/rss/allArticle.xml", keyword_filter=False),
    RssFeed("식품음료신문", "http://www.thinkfood.co.kr/rss/allArticle.xml", keyword_filter=False),
    RssFeed("푸드투데이", "https://www.foodtoday.or.kr/data/rss/news.xml", keyword_filter=False),
    RssFeed("헬로티", "https://www.hellot.net/data/rss/news.xml", keyword_filter=True),
]

# 해외 폴백 풀 — 푸드테크 전문 매체
OVERSEAS_FEEDS: list[RssFeed] = [
    RssFeed("AgFunder News", "https://agfundernews.com/feed", keyword_filter=False),
    RssFeed("Green Queen", "https://www.greenqueen.com.hk/feed/", keyword_filter=False),
    RssFeed("Food Dive", "https://www.fooddive.com/feeds/news/", keyword_filter=False),
    RssFeed(
        "FoodNavigator",
        "https://www.foodnavigator.com/arc/outboundfeeds/rss/",
        keyword_filter=False,
    ),
]

# keyword_filter=True 피드에 적용하는 후처리 키워드 (제목+요약 부분일치, 대소문자 무시)
FILTER_KEYWORDS: list[str] = [
    "푸드테크",
    "식품",
    "먹거리",
    "농식품",
    "배양육",
    "대체육",
    "스마트팜",
    "외식",
    "급식",
    "콜드체인",
    "food",
    "agri",
]

GOOGLE_NEWS_RSS_EN = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

NAVER_NEWS_API = "https://openapi.naver.com/v1/search/news.json"
BRAVE_SEARCH_API = "https://api.search.brave.com/res/v1/web/search"
