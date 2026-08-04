"""뉴스 수집 소스 레지스트리.

검색 쿼리는 네이버(국내)·Brave(해외)·Google News RSS(해외 폴백)가 공유한다 (T-001 AC4).
카테고리는 정부 "푸드테크 10대 핵심분야" 체계를 따른다 (CLAUDE.md 결정 2).
피드 URL은 docs/research/news-sources.md에서 2026-07-12 fetch 검증된 것만 싣는다.
"""

from typing import NamedTuple
from urllib.parse import urlparse


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


# ---------------------------------------------------------------- 매체명 (T-018)
#
# 네이버·Brave API 응답에는 매체명 필드가 없다 — 수집기가 "source": ""를 넣어왔고,
# 그 결과 news_items 460건이 전부 출처 없이 쌓였다(2026-08-04 확인). 뉴스레터에도
# "KR"로만 표시된다. URL 호스트에서 되살린다.
#
# **확실한 매체만 적는다.** 틀린 이름을 붙이는 건 도메인을 그대로 보여주는 것보다 나쁘다 —
# 나머지는 도메인 폴백에 맡기고, 자주 등장하는 게 보이면 여기에 추가한다.
SOURCE_BY_DOMAIN: dict[str, str] = {
    # 종합·경제 일간
    "chosun.com": "조선일보",
    "biz.chosun.com": "조선비즈",
    "donga.com": "동아일보",
    "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "seoul.co.kr": "서울신문",
    "kmib.co.kr": "국민일보",
    "munhwa.com": "문화일보",
    "segye.com": "세계일보",
    "naeil.com": "내일신문",
    "shinailbo.co.kr": "신아일보",
    "hankookilbo.com": "한국일보",
    "hankooki.com": "한국일보",
    "daily.hankooki.com": "한국일보",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "mt.co.kr": "머니투데이",
    "sedaily.com": "서울경제",
    "edaily.co.kr": "이데일리",
    "fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제",
    "heraldcorp.com": "헤럴드경제",
    "biz.heraldcorp.com": "헤럴드경제",
    "dnews.co.kr": "대한경제",
    "ekn.kr": "에너지경제",
    "viva100.com": "브릿지경제",
    "cstimes.com": "컨슈머타임스",
    "breaknews.com": "브레이크뉴스",
    # 통신·방송
    "yna.co.kr": "연합뉴스",
    "news1.kr": "뉴스1",
    "newsis.com": "뉴시스",
    "ytn.co.kr": "YTN",
    "kbs.co.kr": "KBS",
    "imbc.com": "MBC",
    "sbs.co.kr": "SBS",
    # IT·산업
    "etnews.com": "전자신문",
    "dt.co.kr": "디지털타임스",
    "zdnet.co.kr": "ZDNet Korea",
    "aving.net": "AVING",
    "kr.aving.net": "AVING",
    # 식품·농축수산 전문지
    "foodnews.co.kr": "식품음료신문",
    "thinkfood.co.kr": "식품외식경제",
    "aflnews.co.kr": "농수축산신문",
    "foodbank.co.kr": "월간식당",
    # 공공
    "kotra.or.kr": "KOTRA 해외시장뉴스",
    "dream.kotra.or.kr": "KOTRA 해외시장뉴스",
    # 해외
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "foodnavigator.com": "FoodNavigator",
    "fooddive.com": "Food Dive",
    "agfundernews.com": "AgFunderNews",
    "digitalfoodlab.com": "DigitalFoodLab",
}

# 호스트 앞에 붙어 매체를 바꾸지 않는 접두사 (biz.chosun.com은 조선비즈라 여기 없다 — 매핑 우선)
_STRIP_PREFIXES = ("www.", "m.", "news.", "view.", "amp.")


def source_from_url(url: str) -> str:
    """URL 호스트에서 매체명을 되살린다. 모르는 곳이면 도메인을 그대로 돌려준다.

    매핑은 전체 호스트 → 접두사 제거 → 상위 도메인 순으로 찾는다.
    biz.chosun.com(조선비즈)과 chosun.com(조선일보)이 다른 매체라 전체 호스트가 먼저다.
    """
    if not url:
        return ""
    host = urlparse(url).netloc.lower().split(":")[0]
    if not host:
        return ""

    if host in SOURCE_BY_DOMAIN:
        return SOURCE_BY_DOMAIN[host]

    stripped = host
    for prefix in _STRIP_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :]
            break
    if stripped in SOURCE_BY_DOMAIN:
        return SOURCE_BY_DOMAIN[stripped]

    # 서브도메인을 한 겹씩 벗겨가며 등록된 도메인을 찾는다 (news.abc.co.kr → abc.co.kr)
    parts = stripped.split(".")
    for i in range(1, len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in SOURCE_BY_DOMAIN:
            return SOURCE_BY_DOMAIN[candidate]

    return stripped  # 모르는 매체 — 빈칸보다 도메인이 낫다
