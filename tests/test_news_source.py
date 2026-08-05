"""매체명 복원 (T-018).

네이버·Brave 응답에 매체명 필드가 없어 수집기가 빈 문자열을 넣어왔다. URL 호스트에서 되살린다.
설계 원칙: **모르면 지어내지 않는다** — 매핑에 없으면 도메인을 그대로 돌려준다.
"""

import pytest

from app.services.news_sources import SOURCE_BY_DOMAIN, source_from_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # 같은 회사라도 서브도메인이 다른 매체면 다르게 잡아야 한다
        ("https://biz.chosun.com/site/data/1.html", "조선비즈"),
        ("https://www.chosun.com/national/1", "조선일보"),
        # www 등 무의미한 접두사는 벗긴다
        ("https://www.mt.co.kr/news/1", "머니투데이"),
        ("https://mt.co.kr/news/1", "머니투데이"),
        # 매핑에 서브도메인째 등록된 경우
        ("https://daily.hankooki.com/news/1", "한국일보"),
        ("https://dream.kotra.or.kr/user/1", "KOTRA 해외시장뉴스"),
        # 등록 안 된 서브도메인은 상위 도메인으로 내려가며 찾는다
        ("https://sports.donga.com/1", "동아일보"),
        # 해외
        ("https://www.foodnavigator.com/Article/1", "FoodNavigator"),
        # 포트가 붙어도 무시
        ("https://www.yna.co.kr:443/view/1", "연합뉴스"),
    ],
)
def test_known_outlets_are_named(url: str, expected: str):
    assert source_from_url(url) == expected


def test_unknown_outlet_falls_back_to_domain():
    """모르는 매체는 도메인을 그대로 — 빈칸보다 낫고, 틀린 이름보다는 훨씬 낫다."""
    assert source_from_url("https://www.no-such-outlet.co.kr/news/1") == "no-such-outlet.co.kr"
    assert source_from_url("https://unmapped.example/news/1") == "unmapped.example"


def test_empty_and_malformed_urls_are_safe():
    assert source_from_url("") == ""
    assert source_from_url("not-a-url") == ""


def test_mapping_values_are_not_blank():
    """빈 매체명이 섞이면 폴백보다 나쁜 결과가 조용히 나간다."""
    assert all(name.strip() for name in SOURCE_BY_DOMAIN.values())


def test_mapping_keys_are_bare_hosts():
    """키에 스킴이나 경로가 섞이면 영영 매칭되지 않는다."""
    for domain in SOURCE_BY_DOMAIN:
        assert "/" not in domain and domain == domain.lower()
