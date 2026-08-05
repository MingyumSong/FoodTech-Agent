"""기사 큐레이션 — 같은 사건의 중복 기사를 하나로 묶는다 (T-009).

왜 필요한가: 기업 보도자료를 여러 매체가 받아쓰면 URL도 제목도 달라서 코드 입장에선
별개 기사가 된다. 실측(2026-08-05, 최근 7일 158건)에서 "BBQ 오븐구이 닭다리살 롯데마트
입점" 하나가 4개 매체로 들어와 있었고, 풀의 13.9%가 이런 중복이었다.
하루 5꼭지짜리 뉴스레터에서 두 칸이 같은 뉴스면 독자 눈엔 성의 없는 편지다.

파일럿의 분야 distinct 회전(`pilot_daily._take_rotated`)으로는 못 막는다 —
같은 사건을 LLM이 매체마다 다른 분야로 분류하기 때문이다(매일유업 콩물두유:
식물기반식품 1건 + 일반 2건). 분야가 다르니 "겹침 방지"를 그대로 통과한다.

설계:
- 제목 토큰 자카드 유사도 ≥ THRESHOLD 면 같은 사건으로 본다. 단 **연쇄로 잇지 않는다** —
  대표와 직접 닮은 것만 한 군집이다(`cluster_of` 참조. 초안은 연결요소였는데 드라이런에서
  묶음기사가 다리가 돼 서로 다른 두 사건이 뭉치는 걸 보고 바꿨다).
- 군집마다 대표 1건만 남긴다. 대표는 **선호 매체 우선**(`news_sources.source_tier`) —
  같은 사건 안에서의 선택이라 분야 다양성 비용이 0인데, 지역지 대신 뉴스1을 고르는
  이득은 그대로 얻는다 (파일럿 #0의 지역지 모바일 미개봉 사고가 이 경로였다).
- 신뢰도를 **거르는 데는 쓰지 않는다**: 매핑률이 얇아(해외 15건 중 1건) 필터로 쓰면
  분야·해외 꼭지가 굶는다. 자세한 근거는 티켓 T-009.
"""

import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.services.news_sources import source_tier

# 임계값 근거(실데이터 158건 측정): 0.30~0.40 구간 12쌍은 전부 진짜 중복이었고,
# 오검출은 0.28에서 시작했다("제주테크노파크 제조혁신" vs "천안 학화호두과자 스마트공장"
# — 서로 다른 사건인데 스마트공장·AI·제조·혁신 같은 일반어만 겹쳤다).
# 여유가 0.02로 얇은 걸 알고 고른 값이다. 근거는 비용 비대칭: 풀 158건에서 5건만 쓰므로
# 과병합 손실은 거의 0이고, 미병합은 독자 눈에 바로 보이는 실패다.
SIMILARITY_THRESHOLD = 0.30

# 뉴스 제목에 흔해서 사건을 구분해주지 못하는 말. 여기 넣을수록 판별이 예민해진다.
_STOPWORDS = frozenset(
    {
        "기자", "뉴스", "종합", "속보", "단독", "포토", "영상", "인터뷰", "기고",
        "주", "개", "년", "월", "일", "및", "등", "위해", "통해", "대한", "있다", "한다",
    }
)  # fmt: skip

_BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)")  # [단독] (종합) 류 말머리
_NON_WORD = re.compile(r"[^0-9A-Za-z가-힣]+")
_HANGUL_ONLY = re.compile(r"^[가-힣]+$")


def title_tokens(title: str) -> frozenset[str]:
    """제목을 비교용 토큰 집합으로. 임계값이 이 함수에 맞춰 측정됐으니 같이 바꿔야 한다.

    한국어는 조사가 붙어 '오뚜기'와 '오뚜기가'가 다른 토큰이 된다 → 끝 한 글자를 뗀
    어간도 **함께** 넣어 두 형태를 잇는다(치환이 아니라 추가 — 집합 크기가 커지는 만큼
    임계값이 낮게 잡혀 있다).
    """
    cleaned = _NON_WORD.sub(" ", _BRACKETS.sub(" ", title or ""))
    out: set[str] = set()
    for word in cleaned.split():
        if len(word) < 2 or word in _STOPWORDS:
            continue
        out.add(word.lower())
        if len(word) > 2 and _HANGUL_ONLY.match(word):
            out.add(word[:-1].lower())
    return frozenset(out)


# 여러 사건을 한 편에 몰아 쓴 기사 = 묶음기사. 카드 하나가 기사 하나를 가리켜야 하는
# 뉴스레터에선 링크로 못 쓴다. 게다가 여러 사건을 동시에 언급해서 **중복 판정의 다리**가 된다
# (실측: "매일유업 콩물두유→오뚜기 닭한마리"가 서로 다른 두 사건을 한 군집으로 묶었다).
#
# 표지 정밀도(2026-08-05, 30일 460건): 15건 적중 = 3.3%. 그중 13건이 다항목 묶음이고
# 나머지 2건도 "[고려대 소식]"류 브리핑성 단신이라 카드감이 아니다. 오검출 0건.
_ROUNDUP_TAIL = re.compile(r"(\s외|\s外)\s*$")  # "…롯데웰푸드 外" — 뒤에 더 있다는 표시
_ROUNDUP_ARROW = re.compile(r"→")  # "A 신제품→B 신제품"
_ROUNDUP_BRACKET = re.compile(
    r"^\s*[\[\(【][^\]\)】]*"
    r"(소식|브리핑|모음|weekly|주간|now|유통가|한눈에|종합|신상품|잘먹잘살|굿모닝|투데이)"
    r"[^\]\)】]*[\]\)】]",
    re.I,
)


def is_roundup(title: str) -> bool:
    """여러 사건을 묶어 쓴 기사인가 — 뉴스레터 카드로 쓰지 않는다."""
    t = title or ""
    return bool(_ROUNDUP_TAIL.search(t) or _ROUNDUP_ARROW.search(t) or _ROUNDUP_BRACKET.search(t))


def similarity(a: str, b: str) -> float:
    """두 제목의 자카드 유사도 (0.0 ~ 1.0)."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cluster_of(records: Sequence[tuple[str, str, str]]) -> list[list[int]]:
    """같은 사건끼리 묶는다. 각 군집의 **첫 원소가 대표**다.

    **연쇄(single-linkage)를 쓰지 않는다.** 대표와 직접 닮은 기사만 같은 사건으로 본다.
    이유는 실측이다(2026-08-05 운영 7일 풀): 여러 사건을 한 편에 묶어 쓴 기사
    ("매일유업 콩물두유→오뚜기 닭한마리 칼국수")가 다리가 돼서 **서로 다른 두 사건**이
    한 군집(7건)으로 뭉쳤다. A~B, B~C가 이어져도 A~C는 다른 사건일 수 있다.

    대표 선정 우선순위:
      1. `source_tier` — 선호 매체(0) > 이름 아는 매체(1) > 모르는 곳(2).
         뉴스1 vs 전라일보면 뉴스1이 뽑힌다.
      2. 요약이 긴 것 — 카드에 실을 내용이 있는 쪽
      3. 입력이 빠른 것 — 호출부가 최신순으로 넘기므로 더 최신
    """
    toks = [title_tokens(r[0]) for r in records]
    # tier를 미리 계산해둔다 — min()이 매 루프마다 전 항목에 source_tier를 다시 부르면
    # urlparse가 n^2/2회 돈다(실측 1,264건에서 80만 회·2.5초). 한 번씩만 부르면 사라진다.
    tiers = [source_tier(r[1]) for r in records]
    lengths = [-len(r[2] or "") for r in records]
    remaining = set(range(len(records)))
    groups: list[list[int]] = []

    while remaining:
        lead = min(remaining, key=lambda i: (tiers[i], lengths[i], i))
        remaining.discard(lead)
        group = [lead]
        for i in sorted(remaining):
            ti, tl = toks[i], toks[lead]
            if not ti or not tl:
                continue
            if len(ti & tl) / len(ti | tl) >= SIMILARITY_THRESHOLD:
                group.append(i)
        remaining.difference_update(group)
        groups.append(group)
    return groups


def dedupe_indices(records: Sequence[tuple[str, str, str]]) -> list[int]:
    """중복을 병합하고 남길 인덱스를 **입력 순서 그대로** 반환한다.

    records = (제목, URL, 요약). 인덱스만 돌려주므로 호출부가 NewsItem이든 dict든 상관없다.
    """
    if len(records) < 2:
        return list(range(len(records)))
    return sorted(group[0] for group in cluster_of(records))


class _Article(Protocol):
    """제목·URL·요약을 가진 것 — NewsItem이든 무엇이든.

    읽기 전용 property로 선언한다. 속성으로 쓰면 불변(invariant)이라
    `summary: str`인 NewsItem이 `str | None` 프로토콜에 안 맞는다.
    """

    @property
    def title(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def summary(self) -> str | None: ...


def curate_dicts(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """`_item_dict` 형태의 풀을 큐레이션한다 — 묶음기사 제외 후 중복 병합 (파일럿 경로)."""
    pool = [it for it in items if not is_roundup(it.get("title") or "")]
    keep = dedupe_indices(
        [(it.get("title") or "", it.get("url") or "", it.get("summary") or "") for it in pool]
    )
    return [pool[i] for i in keep]


def curate_articles[ArticleT: _Article](items: Sequence[ArticleT]) -> list[ArticleT]:
    """NewsItem 등 객체 목록을 큐레이션한다 (주간 조립 경로)."""
    pool = [it for it in items if not is_roundup(it.title or "")]
    keep = dedupe_indices([(it.title or "", it.url or "", it.summary or "") for it in pool])
    return [pool[i] for i in keep]
