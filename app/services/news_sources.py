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
    "etoday.co.kr": "이투데이",
    "newspim.com": "뉴스핌",
    "seoulfn.com": "서울파이낸스",
    "finomy.com": "현대경제신문",
    "businesskorea.co.kr": "Businesskorea",
    "m-economynews.com": "M이코노미뉴스",
    "megaeconomy.co.kr": "메가경제",
    "financialreview.co.kr": "파이낸셜리뷰",
    "startuptoday.co.kr": "오늘경제",
    "goodkyung.com": "굿모닝경제",
    "thepowernews.co.kr": "더파워",
    "biztribune.co.kr": "비즈트리뷴",
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
    "hellot.net": "헬로티",
    "handmk.com": "핸드메이커",
    "digitalchosun.dizzo.com": "디지틀조선일보",
    # 종합·지역·기타 (2026-08-05 실수집분에서 반복 등장 — 각 사이트 <title>로 확인)
    "tf.co.kr": "더팩트",
    "enewstoday.co.kr": "이뉴스투데이",
    "news2day.co.kr": "뉴스투데이",
    "newscj.com": "천지일보",
    "newsworker.co.kr": "뉴스워커",
    "inthenews.co.kr": "인더뉴스",
    "beyondpost.co.kr": "비욘드포스트",
    "thefirstmedia.net": "더퍼스트미디어",
    "thefairnews.co.kr": "더페어",
    "pressman.kr": "프레스맨",
    "press9.kr": "PRESS9",
    "pointdaily.co.kr": "포인트데일리",
    "fieldnews.kr": "필드뉴스",
    "livesnews.com": "라이브뉴스",
    "livebiz.today": "생생비즈플러스",
    "slist.kr": "싱글리스트",
    "lawissue.co.kr": "로이슈",
    "polinews.co.kr": "폴리뉴스",
    "lecturernews.com": "한국강사신문",
    "dhnews.co.kr": "대학저널",
    # 지역 일간
    "incheonilbo.com": "인천일보",
    "kado.net": "강원도민일보",
    "ggilbo.com": "금강일보",
    "jeollailbo.com": "전라일보",
    "sjbnews.com": "새전북신문",
    "jejusori.net": "제주의소리",
    "gnnews.co.kr": "경남일보",
    "dynews.co.kr": "동양일보",
    # 식품·농축수산 전문지
    # ⚠️ 이 셋은 T-018에서 한 칸씩 밀려 있었다(foodnews→식품음료신문, thinkfood→식품외식경제,
    # foodbank→월간식당). 2026-08-05 각 사이트 <title>로 직접 확인해 바로잡았다.
    "foodnews.co.kr": "식품저널",
    "thinkfood.co.kr": "식품음료신문",
    "foodbank.co.kr": "식품외식경제",
    "aflnews.co.kr": "농수축산신문",
    "foodtoday.or.kr": "푸드투데이",
    "fsnews.co.kr": "대한급식신문",
    "agrinet.co.kr": "한국농어민신문",
    "newsfarm.co.kr": "한국농업신문",
    "realfoods.co.kr": "리얼푸드",
    "vegannews.co.kr": "비건뉴스",
    "kdfnews.com": "한국면세뉴스",
    # 공공
    "kotra.or.kr": "KOTRA 해외시장뉴스",
    "dream.kotra.or.kr": "KOTRA 해외시장뉴스",
    # 해외
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "fortune.com": "Fortune",
    "gizmodo.com": "Gizmodo",
    "foodnavigator.com": "FoodNavigator",
    "fooddive.com": "Food Dive",
    "agfundernews.com": "AgFunderNews",
    "digitalfoodlab.com": "DigitalFoodLab",
    "greenqueen.com.hk": "Green Queen",
    "vegconomist.com": "vegconomist",
    "nutritioninsight.com": "Nutrition Insight",
    "restaurantbusinessonline.com": "Restaurant Business",
    "foodandbeverage.business": "Food & Beverage Business",
    "thedieline.com": "DIELINE",
    # 2026-08-18 추가 — 최근 30일 발송·수집분에서 **도메인이 그대로 메일에 찍히던** 곳들.
    # 각 사이트 <title>로 직접 확인했다(youngnong.co.kr은 응답이 없어 뺐다 — 확실한 것만 적는다).
    "economist.co.kr": "이코노미스트",
    "ajunews.com": "아주경제",
    "idaegu.com": "대구일보",
    "m-i.kr": "매일일보",
    "asiatoday.co.kr": "아시아투데이",
    "4th.kr": "포쓰저널",
    "nongmin.com": "농민신문",
    "getnews.co.kr": "글로벌경제신문",
    "g-enews.com": "글로벌이코노믹",
    "dailian.co.kr": "데일리안",
    "newsway.co.kr": "뉴스웨이",
    "amnews.co.kr": "농축유통신문",
}

# 링크를 걸고 싶은 매체 — 중복 군집에서 대표를 고를 때 우선한다 (T-009).
#
# **위 사전과 목적이 다르다.** SOURCE_BY_DOMAIN은 "이름을 아는가"(표시용)라서 지역지·소규모
# 매체까지 넓게 담는다. 이 목록은 "같은 사건이면 여기로 링크하고 싶은가"(편집 판단)다.
# 사전이 넓어질수록 매핑 여부는 신뢰 신호가 못 되므로 목록을 따로 둔다.
# 판단 근거: 파일럿 #0에서 지역지(금강일보) 기사가 모바일에서 안 열려 독자가 허탕 쳤다.
PREFERRED_SOURCE_DOMAINS: frozenset[str] = frozenset(
    {
        # 통신·방송
        "yna.co.kr", "news1.kr", "newsis.com", "ytn.co.kr", "kbs.co.kr", "imbc.com", "sbs.co.kr",
        # 종합 일간
        "chosun.com", "biz.chosun.com", "donga.com", "joongang.co.kr", "hani.co.kr",
        "khan.co.kr", "seoul.co.kr", "kmib.co.kr", "munhwa.com", "segye.com",
        "hankookilbo.com", "hankooki.com", "daily.hankooki.com", "naeil.com",
        # 경제
        "hankyung.com", "mk.co.kr", "mt.co.kr", "sedaily.com", "edaily.co.kr", "fnnews.com",
        "asiae.co.kr", "heraldcorp.com", "biz.heraldcorp.com", "dnews.co.kr", "ekn.kr",
        "etoday.co.kr", "newspim.com",
        # IT·산업
        "etnews.com", "dt.co.kr", "zdnet.co.kr",
        # 식품·농축수산 전문지 — 주제 적합도가 높아 선호
        "foodnews.co.kr", "thinkfood.co.kr", "foodbank.co.kr", "aflnews.co.kr",
        "foodtoday.or.kr", "agrinet.co.kr", "newsfarm.co.kr", "fsnews.co.kr",
        # 공공
        "kotra.or.kr", "dream.kotra.or.kr",
        # 해외
        "reuters.com", "bloomberg.com", "fortune.com", "foodnavigator.com", "fooddive.com",
        "agfundernews.com", "greenqueen.com.hk", "vegconomist.com", "nutritioninsight.com",
        "restaurantbusinessonline.com",
    }
)  # fmt: skip

# 호스트 앞에 붙어 매체를 바꾸지 않는 접두사 (biz.chosun.com은 조선비즈라 여기 없다 — 매핑 우선)
_STRIP_PREFIXES = ("www.", "m.", "news.", "view.", "amp.")


def _stripped_host(url: str) -> str:
    """URL의 호스트에서 매체를 바꾸지 않는 접두사만 뗀 것. 없으면 빈 문자열."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower().split(":")[0]
    for prefix in _STRIP_PREFIXES:
        if host.startswith(prefix):
            return host[len(prefix) :]
    return host


def _host_candidates(url: str) -> list[str]:
    """조회 키 후보를 좁은 것부터 넓은 순으로. 전체 호스트 → 접두사 제거 → 상위 도메인.

    biz.chosun.com(조선비즈)과 chosun.com(조선일보)이 다른 매체라 전체 호스트가 먼저다.
    """
    if not url:
        return []
    host = urlparse(url).netloc.lower().split(":")[0]
    if not host:
        return []

    stripped = _stripped_host(url)
    out = [host] if stripped == host else [host, stripped]
    # 서브도메인을 한 겹씩 벗겨가며 찾는다 (news.abc.co.kr → abc.co.kr)
    parts = stripped.split(".")
    out.extend(".".join(parts[i:]) for i in range(1, len(parts) - 1))
    return out


def source_from_url(url: str) -> str:
    """URL 호스트에서 매체명을 되살린다. 모르는 곳이면 도메인을 그대로 돌려준다."""
    for key in _host_candidates(url):
        if key in SOURCE_BY_DOMAIN:
            return SOURCE_BY_DOMAIN[key]
    return _stripped_host(url)  # 모르는 매체 — 빈칸보다 도메인이 낫다


def source_tier(url: str) -> int:
    """링크 선호도 — 0=선호 매체, 1=이름은 아는 매체, 2=모르는 곳. **낮을수록 우선.**

    중복 군집에서 대표를 고를 때만 쓴다(T-009). 거르는 데는 쓰지 않는다 —
    매핑률이 얇아(해외 15건 중 1건) 필터로 쓰면 분야·해외 꼭지가 굶는다.
    """
    candidates = _host_candidates(url)
    if any(key in PREFERRED_SOURCE_DOMAINS for key in candidates):
        return 0
    if any(key in SOURCE_BY_DOMAIN for key in candidates):
        return 1
    return 2
