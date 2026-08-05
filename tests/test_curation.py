"""T-009 기사 큐레이션 — 중복 병합·대표 선정.

제목은 전부 2026-08-05 운영 DB 실수집분에서 가져왔다. 임계값(0.30)이 이 데이터로
측정된 값이라, 여기 제목을 바꾸면 임계값 근거도 같이 무너진다.
"""

from app.services.curation import (
    SIMILARITY_THRESHOLD,
    curate_articles,
    curate_dicts,
    dedupe_indices,
    is_roundup,
    similarity,
)
from app.services.news_classify import is_non_news_url
from app.services.news_sources import source_from_url, source_tier

# 실제로 4개 매체가 같은 보도자료를 받아쓴 사건
BBQ = [
    ("BBQ, HMR '오븐구이 닭다리살' 롯데마트 입점…오프라인 판매 확대", "https://kdfnews.com/1"),
    ("BBQ, '오븐구이 닭다리살' 롯데마트 입점", "https://www.megaeconomy.co.kr/2"),
    ("BBQ, HMR 유통망 확대... '오븐구이 닭다리살' 롯데마트 입점", "https://thefirstmedia.net/3"),
    ("BBQ, 간편식 '오븐구이 닭다리살' 롯데마트 입점", "https://www.inthenews.co.kr/4"),
]


def _rec(title: str, url: str, summary: str = "") -> tuple[str, str, str]:
    return (title, url, summary)


def test_ac1_same_event_across_categories_merges():
    """AC1: 같은 사건이 서로 다른 분야로 분류돼도 한 건으로 병합된다.

    실제 사례 — "매일유업 상하목장 콩물두유"가 plant_based 1건 + general 2건으로 분류됐다.
    분야 distinct 회전(_take_rotated)은 분야가 다르면 못 막으므로 여기서 걸러야 한다.
    """
    pool = [
        {
            "title": "[신상품] 매일유업 상하목장 '콩물두유 서리태' 외",
            "url": "https://www.seoulfn.com/1",
            "summary": "매일유업이 상하목장 콩물두유 서리태를 출시했다",
            "category": "plant_based",
        },
        {
            "title": "매일유업 상하목장, '콩물두유' 3종 출시…프리미엄 두유 시장 진출",
            "url": "https://www.inthenews.co.kr/2",
            "summary": "매일유업이 프리미엄 두유 시장에 진출한다",
            "category": "general",
        },
        {
            "title": "매일유업 상하목장, 첫 두유 라인업...프리미엄 시장 공략",
            "url": "https://www.newspim.com/3",
            "summary": "매일유업 상하목장이 첫 두유 라인업을 선보였다",
            "category": "general",
        },
    ]
    kept = curate_dicts(pool)
    assert len(kept) == 1, "같은 사건 3건이 병합되지 않았다"


def test_ac1_roundup_does_not_bridge_two_different_events():
    """AC1 회귀: 여러 사건을 묶어 쓴 기사가 서로 다른 사건을 한 군집으로 잇지 않는다.

    실측 사고(2026-08-05): "매일유업 콩물두유→오뚜기 닭한마리"가 다리가 돼서
    오뚜기 사건과 매일유업 사건이 7건짜리 한 덩어리로 뭉쳤다. 연쇄(single-linkage)를
    쓰면 A~B, B~C가 이어질 때 A~C가 남남이어도 한 군집이 된다.
    """
    records = [
        _rec("오뚜기 동대문식 닭한마리 칼국수, 50만 개 돌파", "https://www.mt.co.kr/1", "요약"),
        _rec(  # 다리 역할을 하던 묶음기사
            "매일유업 '상하목장 콩물두유'→오뚜기 '동대문식 닭한마리 칼국수'",
            "https://www.slist.kr/2",
            "요약",
        ),
        _rec(
            "매일유업 상하목장, 첫 두유 라인업...프리미엄 시장 공략",
            "https://www.newspim.com/3",
            "요약",
        ),
    ]
    keep = dedupe_indices(records)
    assert 0 in keep and 2 in keep, "서로 다른 두 사건이 하나로 합쳐졌다"


def test_roundup_titles_detected():
    """묶음기사 표지 — 30일 실데이터에서 적중한 형태 그대로."""
    for title in (
        "매일유업 '상하목장 콩물두유'→오뚜기 '동대문식 닭한마리 칼국수'",
        "[Weekly 식품 ·식음료] 풀무원·서울우유·bhc·롯데웰푸드 外",
        "[유통가 NOW] CJ제일제당 연어 스테이크 140만개·오뚜기 닭한마리 칼국수",
        "[신상품] 매일유업 상하목장 '콩물두유 서리태' 외",
        "[굿모닝! 3일 식품업계 소식] 오뚜기·KGC·빙그레·하이트진로·bhc·BBQ",
        "[대학 뉴스브리핑] 고려대·숙명여대·광운대",
        "[8월 3일 캐시워크 돈버는퀴즈 종합]소휘,11번가,리얼마이즈",
    ):
        assert is_roundup(title), f"묶음기사로 걸렸어야 함: {title}"


def test_normal_titles_are_not_roundups():
    """정상 단일 기사는 묶음기사로 오인되지 않는다 — 과차단 회귀 방어.

    '·'는 평범한 병렬 나열('밀·옥수수·올리브유')에도 쓰이고 '···'는 말줄임표라
    구분자 개수로는 판별하지 않는다.
    """
    for title in (
        "폭염이 흔드는 식탁…식품업계, 밀·옥수수·올리브유 등 급등에 원가 부담",
        "경북 미래 식품산업, AI·바이오·K-푸드 융합으로 승부해야",
        "EU 포장 규제 시행 '초읽기'··· 서류 입증 못 하면 수출 막힌다",
        "BBQ, HMR '오븐구이 닭다리살' 롯데마트 입점…오프라인 판매 확대",
        "완주군 특산물 향어, 굿즈로 탄생…'향어 등용문 키링' 제작",
    ):
        assert not is_roundup(title), f"묶음기사가 아님: {title}"


def test_roundups_are_dropped_from_the_pool():
    """묶음기사는 카드로 못 쓰므로 풀에서 빠진다."""
    pool = [
        {
            "title": "[유통가 NOW] CJ제일제당 연어 스테이크 140만개·오뚜기 닭한마리 칼국수",
            "url": "https://www.ekn.kr/1",
            "summary": "요약",
        },
        {
            "title": "배양육 스타트업, 시리즈B 300억 유치",
            "url": "https://www.yna.co.kr/2",
            "summary": "요약",
        },
    ]
    kept = curate_dicts(pool)
    assert [it["title"] for it in kept] == ["배양육 스타트업, 시리즈B 300억 유치"]


def test_ac2_preferred_source_wins_representative():
    """AC2: 중복 군집의 대표는 선호 매체가 된다 (뉴스1 vs 전라일보 → 뉴스1)."""
    records = [
        _rec(
            "완주 특산물 향어가 '등용문 키링'으로",
            "https://www.jeollailbo.com/1",
            "완주군 특산물 향어를 활용한 키링이 제작됐다",
        ),
        _rec(
            "완주군 특산물 향어, 굿즈로 탄생…'향어 등용문 키링' 제작",
            "https://www.news1.kr/2",
            "완주군이 향어를 활용한 굿즈를 제작했다",
        ),
    ]
    keep = dedupe_indices(records)
    assert keep == [1], "선호 매체(뉴스1)가 대표로 뽑히지 않았다"


def test_ac2_preference_beats_longer_summary():
    """선호 매체가 요약 길이보다 우선한다 — 순위 자체를 고정한다."""
    records = [
        _rec("A사, 신형 배양육 반응기 공개", "https://unknown-blog.example/1", "요약" * 200),
        _rec("A사 신형 배양육 반응기 공개했다", "https://www.yna.co.kr/2", "짧은 요약"),
    ]
    assert dedupe_indices(records) == [1]


def test_ac3_cluster_without_preferred_source_still_picks_one():
    """AC3: 선호 매체가 하나도 없는 군집도 대표 1건이 정상 선정된다(굶지 않는다)."""
    records = [_rec(t, u, "요약") for t, u in BBQ]
    assert all(source_tier(u) > 0 for _, u in BBQ), "이 군집엔 선호 매체가 없어야 한다"
    keep = dedupe_indices(records)
    assert len(keep) == 1
    # tier가 같으면 요약 길이 → 입력 순서로 갈린다. 여기선 다 같으므로 첫 번째.
    assert keep == [0]


def test_ac3_cluster_of_entirely_unknown_domains():
    """사전에 아예 없는 도메인들만 있는 군집도 대표가 선정된다."""
    records = [
        _rec("A사, 스마트 콜드체인 실증 착수", "https://tiny1.example/1", "요약"),
        _rec("A사 스마트 콜드체인 실증에 착수했다", "https://tiny2.example/2", "더 긴 요약입니다"),
    ]
    assert all(source_tier(u) == 2 for _, u in [(r[0], r[1]) for r in records])
    assert dedupe_indices(records) == [1]  # tier 동률 → 요약이 긴 쪽


def test_ac3_bbq_four_outlets_merge_to_one():
    """실측된 최대 군집(4건)이 한 덩어리로 묶인다 — 사슬로 이어지는 모양을 확인."""
    records = [_rec(t, u, "요약") for t, u in BBQ]
    assert len(dedupe_indices(records)) == 1


def test_ac6_different_events_sharing_generic_words_not_merged():
    """AC6 회귀: 일반어만 겹치는 서로 다른 사건은 병합되지 않는다.

    실측 오검출 경계(0.28) — 스마트공장·AI·제조·혁신만 공유하는 별개 사건이다.
    임계값을 이 아래로 내리면 이 테스트가 깨진다.
    """
    a = "제주테크노파크, 제조 혁신 4년 연속 A등급… AI 스마트공장 전환 속도"
    b = "천안 학화호두과자, 스마트공장 기반 AI 제조 혁신 본격화"
    assert similarity(a, b) < SIMILARITY_THRESHOLD
    records = [_rec(a, "https://a.example/1"), _rec(b, "https://b.example/2")]
    assert dedupe_indices(records) == [0, 1]


def test_ac6_english_listicles_not_merged():
    """영문 'Top N' 기사끼리도 병합되지 않는다 (실측 0.25 쌍)."""
    a = "Top 20 Companies in Global Food Automation Market"
    b = "Top 10 Industry 4.0 Leaders in Food Processing"
    assert similarity(a, b) < SIMILARITY_THRESHOLD


def test_unrelated_articles_are_untouched():
    """서로 무관한 기사는 순서·개수가 그대로다."""
    records = [
        _rec("CJ제일제당, 식물성 얼티브 새단장", "https://www.hankyung.com/1"),
        _rec("서빙로봇 도입 매장 3만 곳 돌파", "https://www.etnews.com/2"),
        _rec("배양육 스타트업 시리즈B 유치", "https://www.yna.co.kr/3"),
    ]
    assert dedupe_indices(records) == [0, 1, 2]


def test_empty_and_single_inputs():
    assert dedupe_indices([]) == []
    assert dedupe_indices([_rec("단독 기사", "https://a.example/1")]) == [0]


def test_dedupe_preserves_input_order():
    """대표 인덱스는 오름차순 — 호출부의 최신순 정렬이 유지된다."""
    records = [
        _rec("서빙로봇 도입 매장 3만 곳 돌파", "https://www.etnews.com/1"),
        _rec(*BBQ[0], "요약"),
        _rec("배양육 스타트업 시리즈B 유치", "https://www.yna.co.kr/3"),
        _rec(*BBQ[1], "요약"),
    ]
    keep = dedupe_indices(records)
    assert keep == sorted(keep)
    assert len(keep) == 3


def test_dedupe_articles_accepts_objects():
    """NewsItem처럼 title/url/summary 속성을 가진 객체도 그대로 받는다."""

    class _Item:
        def __init__(self, title: str, url: str, summary: str | None):
            self.title, self.url, self.summary = title, url, summary

    items = [_Item(t, u, None) for t, u in BBQ]
    assert len(curate_articles(items)) == 1


# ---- 신뢰도·매체명 (T-009 소스 신뢰도 + T-018 사전 교정) ----------------------------


def test_source_tier_ranks_preferred_above_known_above_unknown():
    assert source_tier("https://www.yna.co.kr/x") == 0  # 선호
    assert source_tier("https://www.jeollailbo.com/x") == 1  # 이름은 아는 지역지
    assert source_tier("https://unknown-blog.example/x") == 2  # 모르는 곳


def test_source_tier_is_not_used_as_a_filter():
    """신뢰도는 거르는 데 쓰지 않는다 — 모르는 곳도 tier가 나올 뿐 탈락하지 않는다.

    매핑률이 얇아(해외 15건 중 1건) 필터로 쓰면 분야·해외 꼭지가 굶는다(AC4).
    """
    unknown = [
        _rec("배양육 반응기 신제품 공개", "https://site1.example/1"),
        _rec("서빙로봇 매장 3만 곳 돌파", "https://site2.example/2"),
        _rec("생분해 포장재 양산 개시", "https://site3.example/3"),
        _rec("맞춤형 영양 구독 서비스 출시", "https://site4.example/4"),
        _rec("커피박 업사이클링 공장 준공", "https://site5.example/5"),
    ]
    assert dedupe_indices(unknown) == [0, 1, 2, 3, 4]


def test_food_trade_press_names_corrected():
    """T-018에서 한 칸씩 밀려 있던 식품 전문지 3곳 — 각 사이트 title로 확인한 값."""
    assert source_from_url("https://www.foodnews.co.kr/news/1") == "식품저널"
    assert source_from_url("https://www.thinkfood.co.kr/news/2") == "식품음료신문"
    assert source_from_url("https://www.foodbank.co.kr/news/3") == "식품외식경제"


def test_unknown_domain_still_falls_back_to_domain():
    """모르는 매체는 여전히 도메인을 돌려준다 — 상위 도메인으로 잘리지 않는다."""
    assert source_from_url("https://www.somewhere.co.kr/news/1") == "somewhere.co.kr"
    assert source_from_url("https://newoutlet.example/a") == "newoutlet.example"


def test_ac5_non_news_domains_blocked():
    """AC5: 논문·보도자료 와이어·레시피 블로그·소셜은 분류 LLM 앞에서 걸러진다."""
    for url in (
        "https://www.frontiersin.org/articles/10.3389/x",
        "https://doi.org/10.1234/abcd",
        "https://www.mdpi.com/2304-8158/1/1/1",
        "https://www.openpr.com/news/1",
        "https://www.eurekalert.org/news-releases/1",
        "https://www.foodnetwork.com/recipes/1",
        "https://www.tiktok.com/@x/video/1",
        "https://news.ycombinator.com/item?id=1",
    ):
        assert is_non_news_url(url), f"차단됐어야 함: {url}"


def test_real_news_domains_not_blocked():
    """정상 매체는 확장된 목록에 걸리지 않는다 — 과차단 회귀 방어."""
    for url in (
        "https://www.yna.co.kr/view/1",
        "https://www.foodnavigator.com/Article/1",
        "https://www.fooddive.com/news/1",
        "https://www.gizmodo.com/1",
        "https://www.hankyung.com/article/1",
    ):
        assert not is_non_news_url(url), f"차단되면 안 됨: {url}"
