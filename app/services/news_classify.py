"""뉴스 LLM 분류·DB 저장 (T-006).

수집된 아이템 중 DB에 없는 URL만 배치로 분류해 news_items에 저장한다.
프롬프트·배치 크기·관대한 파싱은 T-004 드라이런에서 검증된 방식 그대로.
분류 실패는 수집을 막지 않는다 — 실패분은 저장하지 않고 다음 크론에서 재시도된다.
"""

import json
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, col, select

from app.config import settings
from app.db import engine
from app.lib.logger import get_logger
from app.models.news_item import NewsItem

logger = get_logger("news_classify")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
BATCH_SIZE = 20

# 저장 라벨 = 영문 슬러그, LLM I/O = 검증된 한국어 라벨 (T-006 설계 결정 1)
# "해당없음"은 슬러그가 없다 = 저장하지 않는다 (폐기).
SLUG_BY_KO = {
    "세포배양식품": "cell_cultured",
    "식물기반식품": "plant_based",
    "간편식": "convenience",
    "식품프린팅": "food_printing",
    "스마트제조": "smart_manufacturing",
    "스마트유통": "smart_distribution",
    "커스터마이징": "customizing",
    "외식 푸드테크": "food_service",
    "업사이클링": "upcycling",
    "친환경포장": "eco_packaging",
    "일반": "general",
}
KO_BY_SLUG = {v: k for k, v in SLUG_BY_KO.items()}
DISCARD_LABEL = "해당없음"
CATEGORIES_KO = [*SLUG_BY_KO.keys(), DISCARD_LABEL]

# 뉴스가 아님이 확정된 도메인 — LLM 판정 전에 결정적으로 차단(비용·DB 오염 동시 방지).
#
# 2026-08-05(T-009) 대폭 확장. 계기: 30일 해외 수집분의 미매핑 도메인 상위가 전부 비뉴스였다.
# 해외 매체 매핑률이 15건 중 1건이던 건 신뢰도 문제가 아니라 **애초에 뉴스가 아니어서**였다.
# 국내는 네이버 뉴스 API라 이 문제가 거의 없고, Brave는 웹 전체 검색이라 그대로 들어온다.
NON_NEWS_DOMAINS = {
    # 백과·시세
    "wikipedia.org",
    "finance.yahoo.com",
    # 논문·학술 DB — 뉴스레터 독자가 읽을 형식이 아니다(2차 게이트도 '논문'을 버린다)
    "frontiersin.org",
    "mdpi.com",
    "sciencedirect.com",
    "doi.org",
    "springernature.com",
    "stmjournals.com",
    "researchgate.net",
    "arxiv.org",
    "biorxiv.org",
    # 보도자료 배포 와이어·시장보고서 판매 — 기사가 아니라 홍보물이다
    "openpr.com",
    "eurekalert.org",
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "einpresswire.com",
    "marketresearchreports.com",
    "globemarketresearch.com",
    "techversions.com",
    "mordorintelligence.com",
    # 주식 정보·시세 스팸 — 식품 기업명이 걸려 검색에 딸려온다 (2026-08-17 해외 수집분에서 관측)
    "stocktitan.net",
    "tickerreport.com",
    "stockstotrade.com",
    "themarketsdaily.com",
    # 소셜·커뮤니티
    "tiktok.com",
    "youtube.com",
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "ycombinator.com",
    # 레시피·라이프스타일 — 푸드테크 산업 뉴스가 아니다
    "foodnetwork.com",
    "foodandwine.com",
    "allrecipes.com",
    "rainbowplantlife.com",
    "theplantbasedschool.com",
    "cleanplates.com",
    "homediningkitchen.com",
    "precisionnutrition.com",
    # 기업·기관 자사 사이트 (관측된 것만 — 보이는 대로 추가한다)
    "bentosushi.com",
    "opendroids.com",
    "innerbuddies.com",
    "zenmeasure.com",
    "hartdesign.com",
    "magneticgoals.com",
    "kaizen.com",
    "forwardfooding.com",
    "kioskindustry.org",
}

# 판정 순서·예시는 희정 검수(docs/research/뉴스분류_검수완료.md) 오분류 패턴에서 도출.
SYSTEM_PROMPT = f"""당신은 푸드테크 뉴스 분류기다. 각 기사를 정부 "푸드테크 10대 핵심분야"
중 하나로 분류하되, '식품 산업의 기술·산업 뉴스'가 아니면 과감히 "해당없음"으로 버려라.
기본값은 버리는 쪽이다 — 뉴스는 넉넉히 수집하므로, 조금이라도 애매하면 남기지 말고 버린다.

[10대 핵심분야 — 정부 정의로 판단하라]
- 세포배양식품: 세포를 배양해 만든 고기·식품. 배양액·지지체 신소재, 식감·풍미·대량배양 공정.
- 식물기반식품: 식물성 대체육·대체식품. 분리/구조화 단백, 대체 지방·물성 구현 첨가원료.
- 간편식: K-Food 간편식(밀키트·HMR)의 생산 자동화·포장 개선 기술.
- 식품프린팅: 식품 3D프린팅 — 프린팅 적성·가공기술, 식품 잉크 소재. (의료·산업용 3D프린팅은 아님)
- 스마트제조: 식품 '제조·공장'의 AI·로봇 협동, 제조공정 이물질 검출 푸드센서.
- 스마트유통: 식품 '유통·물류'의 AI 품질판정, IoT 기반 콜드체인·유통 실시간 모니터링.
- 커스터마이징: 개인 질환·유전정보 기반 맞춤 식이설계·관리식 개발.
- 외식 푸드테크: 외식 '매장'의 서빙·조리 로봇, 수요예측 AI, 고객 맞춤 데이터.
- 업사이클링: 농식품 '부산물' 재활용 — 성분 DB, 원료처리 공정, 용도 다양화.
- 친환경포장: 식품 포장의 플라스틱 절감·재활용, PBAT/PLA/PHA 등 생분해 포장재.

[판정 순서]
1. 뉴스 기사 자체가 아니면 → "해당없음": 백과사전·시세·포럼·쿠폰·퀴즈, 소비자 대상
   'best/top/추천 N선'·리스트클·영양/식단 조언 등 독자 서비스성 글, 단순 제품·매장 소개.
2. 식품 산업과 무관하거나 '핵심 대상이 식품임이 확실치 않으면' → "해당없음":
   - 의료·제약·치과·바이오 (바이오·3D프린팅 기술이어도 대상이 식품이 아니면)
   - 화장품·제약·식품 등 여러 분야 공용 범용기술 (식품 전용임이 분명해야 남김)
   - 개별 기업 재무·M&A·펀드·투자유치·주가·실적·노사·지배구조 등 경영 일반
   - 지자체·공공기관 행정·복지·지원사업·상생·CSR, 축제·전시·박람회·시상·창립기념 등 행사·협회 소식
   - 학술 논문·저널 연구 요약, 기술 요소 없는 맛집·레스토랑 소개
3. 위를 통과한 '식품 산업 뉴스'만 핵심 주제가 속한 10대 분야 하나로 분류한다.
   단어("3D프린팅","스마트","친환경","로봇","업사이클링","배양","대체")가 아니라
   **기사가 무엇에 관한 것인지**로 판단하라. 부수 사업·지나가는 한 문장 언급은 근거 아님.
   ★ 분야 키워드가 제목에 박혀 있어도, 그 기사가 1·2번에 걸리면(소비자 추천글, 공공기관·지자체
   사회공헌·상생·행사) 분야로 분류하지 말고 반드시 "해당없음"이다. 키워드보다 1·2번이 우선한다.
4. 식품 산업 뉴스가 맞지만 10대 분야 어디에도 안 맞으면 → "일반" (예: 식품 제조·소재 기술
   개발 일반, 정밀발효, 스마트팜). 단 2번의 버릴 것들은 "일반"이 아니라 "해당없음"이다.
5. 조금이라도 애매하면 → "해당없음".

예시 판정:
- "○○제약, 신약 임상 3상…3D 바이오프린팅 활용" → 해당없음 (의료)
- "도로공사, 김천 샤인머스캣 농가에 상생모델 제시" → 해당없음 (공공기관 CSR)
- "농협은행장, 농식품 펀드 2030년까지 8000억" → 해당없음 (금융·펀드)
- "△△시, 임산부 친환경농산물 지원사업 추진" → 해당없음 (지자체 복지)
- "□□푸드테크협회, 창립 2주년 기념행사" → 해당없음 (행사·협회)
- "최고의 식물성 단백질 공급원, 영양사가 추천" → 해당없음 (소비자 조언글)
- "◇◇식품, 라면 공장에 AI 품질검사 도입" → 스마트제조
- "휴밀, 농식품 부산물로 업사이클링 초코 출시" → 업사이클링
- "3D 식품 프린팅 시장 2035년 180억 달러 전망" → 식품프린팅

허용 카테고리 (이 목록의 문자열을 그대로 사용):
{json.dumps(CATEGORIES_KO, ensure_ascii=False)}

출력은 JSON 배열만. 다른 텍스트·설명·코드펜스 금지. 각 항목마다 reason(기사의 실제 주제
한 문장)을 먼저 쓰고 category를 판정하라:
[{{"id": 0, "reason": "밀키트 신제품 출시 소식", "category": "간편식"}}, ...]"""


def is_non_news_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if any(host == d or host.endswith("." + d) for d in NON_NEWS_DOMAINS):
        return True
    # 경로도 쿼리도 없는 주소는 기사가 아니라 **매체 첫 화면**이다 (T-028).
    # `https://thedieline.com/` 이 그대로 푸디픽 #026의 해외 1꼭지로 나갔다 — 제목이
    # "DIELINE - The Leading Source for Packaging Innovation"이라 기사처럼 보였다.
    # 쿼리는 남긴다 — `example.com/?p=123` 같은 워드프레스 주소는 진짜 기사다.
    return not parsed.path.strip("/") and not parsed.query


def _call_openrouter(
    client: httpx.Client, batch: list[dict[str, Any]], system: str = SYSTEM_PROMPT
) -> str:
    """배치 1개 LLM 호출 — 재시도 포함. 최종 실패는 예외 전파(호출부가 격리).

    system을 바꿔 분류(SYSTEM_PROMPT)와 관련성 게이트(RELEVANCE_GATE_PROMPT)에 재사용한다.

    **temperature=0**: 안 넘기면 모델 기본값이라 같은 입력이 매번 다른 판정을 냈다.
    2026-08-09 같은 풀(112건)로 두 번 돌린 결과가 drop 31건 vs 13건이었고, 두 번째엔
    '건설부동산 AX 기업'·'LG CNS 실적' 같이 프롬프트가 명시로 금지한 것들이 통과했다.
    게이트는 판정 도구라 재현되지 않으면 프롬프트를 고쳐도 고쳤는지 알 수 없다.
    """
    payload = {
        "model": settings.news_classify_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ],
        "max_tokens": 8000,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    resp = None
    for attempt in range(3):
        resp = client.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""
    assert resp is not None
    resp.raise_for_status()
    return ""


def _parse_labels(text: str) -> dict[int, str]:
    """응답에서 JSON 배열을 관대하게 추출. 실패 항목은 누락시킨다 (드라이런과 동일)."""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return {}
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    labels: dict[int, str] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("category") in CATEGORIES_KO and "id" in row:
            labels[int(row["id"])] = row["category"]
    return labels


# ---- 뉴스레터 조립 2차 관련성 게이트 (수집 분류보다 엄격) --------------------------------
# 분류(SYSTEM_PROMPT)는 '어느 분야인가'를 정한다. 게이트는 '뉴스레터에 실을 만한 푸드테크
# 산업 뉴스인가'를 더 높은 기준으로 재판정한다. 분류 v2가 놓치는 소비자 리스트클·영양 조언·
# 식품 관련성 애매 케이스(2026-07-27 검수에서 확인)를 build 단계에서 결정적으로 차단.
RELEVANCE_GATE_PROMPT = """당신은 푸드테크 산업 뉴스레터의 엄격한 게이트키퍼다.
각 기사에 대해 두 가지를 판정하라: 실을지(keep) 뺄지(drop), 그리고 실는다면 심도(depth).
기본값은 drop이다. 아래 KEEP 조건을 '명백히' 충족할 때만 keep. 조금이라도 애매하면 drop.

KEEP — 아래를 모두 충족할 때만:
- 식품·푸드테크 '산업/기업/연구/제품/정책'을 다루는 뉴스 기사이고,
- 대상이 명백히 '식품'이며(제목·요약에서 식품임이 분명), 핵심 주제가 푸드테크 기술·산업이다.

DROP — 하나라도 해당하면:
- 소비자 대상 리스트클·'best/top/추천 N선'·모음글·영양/식단 조언 등 독자 서비스성 콘텐츠
  (주제가 식품·업사이클링·친환경이어도, 블로그/추천글 형식이면 산업 뉴스가 아니므로 drop)
- 행사·축제·전시·문화행사 안내, 지자체 행정·복지·지원사업 소식.
  **지자체장·의원의 예산 확보·국비 건의·정부 부처 방문·간담회는 예외 없이 drop** —
  식품 관련 사업이 목록에 끼어 있어도 기사의 주제는 지역 예산이지 푸드테크가 아니다.
- 의료·제약·치과·바이오 (3D프린팅·바이오 기술이어도 대상이 식품이 아니면 drop)
- 기업 재무·M&A·실적·주가·노사·지배구조 등 일반 경영 뉴스
- 백과사전·시세 페이지·포럼 질문·쿠폰·퀴즈, 기술 요소 없는 단순 제품/매장 소개
- 대상 산업이 식품으로 '확정'되지 않는 범용 기술 기사 — 화장품·제약·식품 등 여러 분야에
  적용될 수 있다고만 하면 drop (식품 전용임이 분명해야 keep)
- 학술 논문·저널 연구 요약 (systematic review, "Optimization of ... Parameters",
  Nature/Frontiers/Springer/MDPI 등 저널·연구소 게재물). 뉴스 기사가 아니면 drop.
- 칼럼·사설·기고·오피니언, 인물 인터뷰(말머리 [인터뷰]·interview·'○○ 대표' 인물 소개),
  [기획연재]·[특집]·[르포] 같은 연재·기획물.
  주장·해설·인물 이야기지 '무슨 일이 일어났는가'를 전하는 기사가 아니면 drop.

DEPTH — keep인 항목의 '심도'를 1~5 정수로 매긴다. 뉴스레터의 '메인'(3꼭지)과
'에피타이저'(2꼭지)를 가르는 값이다. 높을수록 메인에 가깝다.
- 5 = 산업 판도를 바꾸는 사건. 대규모 투자·인수, 규제·표준 제정, 상용화 첫 사례.
- 4 = 의미 있는 기술·설비·연구 진전. 업계가 따라 할 만한 실질적 변화가 있다.
- 3 = 통상적인 산업 뉴스. 사실 전달은 되지만 파급은 제한적이다.
- 2 = 단신. 업무협약(MOU), 단순 입점·판매 개시, 간담회·현장점검, 지역 단위 소식,
      인사·수상, 기존 사실의 재정리.
- 1 = 거의 정보가 없는 홍보성 소식.

**4~5는 인색하게 준다.** 전체의 20%를 넘지 않게 하라 — 메인 자리는 세 칸뿐이다.
애매하면 3 이하.

예시 판정:
- "지구를 구하는 착한 스낵 BEST 10 | ○○매거진" → keep=false (소비자 추천 리스트클, 산업 뉴스 아님)
- "액상 공정을 AI로 실시간 모니터링…화장품·제약·식품 등에 적용" → keep=false (식품 전용 아님)
- "최고의 식물성 단백질 공급원, 영양사가 추천" → keep=false (독자 대상 식단 조언글)
- "[경제인칼럼] 동네상권 위기의 외식업" → keep=false (칼럼)
- "○○지사, 기획예산처장관 만나 미래 핵심사업 국비 지원 건의" → keep=false (지자체 예산 활동)
- "[더벨][interview] 건설부동산 AX 기업 돋보기 — ○○ 대표" → keep=false (인물 인터뷰 + 식품 아님)
- "삼성·SK·현대차, '40도 시대' 생존 기술 경쟁" → keep=false (대상 산업이 식품이 아님)
- "국산 NPU 확산에 600억원 투입…피지컬AI 실증" → keep=false (반도체·AI 일반, 식품 아님)
- "상반기 매출 2.8조 돌파…○○, 남은 숙제는 밸류 재평가" → keep=false (실적·주가 뉴스)
- "3D 식품 프린팅 시장 2035년 180억 달러 전망" → keep=true, depth=4 (시장 판도)
- "○○식품, 라면 공장에 AI 품질검사 도입" → keep=true, depth=4 (제조 기술 도입)
- "aT, 수출지원 간담회 개최" → keep=true, depth=2 (간담회 단신)
- "○○기업, △△마트에 신제품 입점" → keep=true, depth=2 (단순 입점)

출력은 JSON 배열만. 각 항목에 reason(판정 근거 한 문장)을 먼저 쓰고 keep, 그리고 keep일 때 depth:
[{"id": 0, "reason": "식품 3D프린팅 시장 전망 기사", "keep": true, "depth": 4},
 {"id": 1, "reason": "소비자 추천 리스트클", "keep": false}, ...]"""

# 심도 판정 없음(게이트 실패·키 없음)은 0. 정렬에서 '가벼움'과 같은 자리에 둬서
# 판정이 아예 없으면 기존 순서가 그대로 유지되게 한다.
DEPTH_NONE = 0
DEPTH_MIN, DEPTH_MAX = 1, 5


def _depth_of(raw: Any) -> int:
    """심도 값을 1~5 정수로. 범위 밖·형식 위반은 `DEPTH_NONE`(판정 없음)으로 떨어뜨린다.

    이상한 값을 최저점으로 때우지 않는다 — 호출부가 '판정 실패'와 '가벼운 기사'를
    구분해야 게이트가 죽었을 때 기존 순서로 되돌아갈 수 있다.
    """
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEPTH_NONE
    return n if DEPTH_MIN <= n <= DEPTH_MAX else DEPTH_NONE


def _parse_gate(text: str) -> dict[int, tuple[bool, int]]:
    """`{id: (keep, depth)}` — depth 0은 판정 없음."""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return {}
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    out: dict[int, tuple[bool, int]] = {}
    for row in rows:
        if isinstance(row, dict) and "id" in row and "keep" in row:
            out[int(row["id"])] = (bool(row["keep"]), _depth_of(row.get("depth")))
    return out


def _gate_batch(
    items: list[dict[str, Any]], client: httpx.Client
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """청크 하나를 판정한다 — 실패하면 **그 청크만** 전량 통과(보수적).

    id는 청크 안에서만 유효한 지역 색인이다. 청크마다 0부터 다시 매기므로
    호출부가 오프셋을 되돌릴 필요가 없다.
    """
    batch = [
        {"id": i, "title": it.get("title") or "", "summary": (it.get("summary") or "")[:300]}
        for i, it in enumerate(items)
    ]
    verdict = _parse_gate(_call_openrouter(client, batch, system=RELEVANCE_GATE_PROMPT))
    if not verdict:  # 빈/깨진 응답 간헐 재현 대비 1회 재시도 (분류와 동일 방어)
        verdict = _parse_gate(_call_openrouter(client, batch, system=RELEVANCE_GATE_PROMPT))
    if not verdict:
        return list(items), []  # 게이트 자체가 실패하면 원본 유지(빈 뉴스레터 방지)

    kept, dropped = [], []
    for i, it in enumerate(items):
        keep, depth = verdict.get(i, (True, DEPTH_NONE))
        if not keep:
            dropped.append(it)
        else:
            kept.append({**it, "depth": depth} if depth else it)
    return kept, dropped


def _log_gate_verdict(kept: list[dict[str, Any]], dropped: list[dict[str, Any]]) -> None:
    """게이트가 무엇을 걸렀는지 로그에 남긴다 — 판정을 DB에 안 남기므로 여기가 유일한 기록이다.

    왜 필요한가: 게이트가 조용히 무력화돼도(T-028) 숫자만 보면 '발송 성공'이라 아무도 모른다.
    같은 입력을 다시 태워도 답이 달라지므로 사후 재구성이 안 된다 — 그 순간의 판정을 남긴다.
    """
    depths: dict[int, int] = {}
    for it in kept:
        d = it.get("depth")
        depths[d if isinstance(d, int) else DEPTH_NONE] = (
            depths.get(d if isinstance(d, int) else DEPTH_NONE, 0) + 1
        )
    logger.info(
        f"gate verdict: keep={len(kept)} drop={len(dropped)} "
        f"depth={dict(sorted(depths.items(), reverse=True))}"
    )
    if not dropped:
        # drop 0은 정상일 수도, 게이트가 죽은 것일 수도 있다. 풀이 크면 후자가 훨씬 흔하다.
        logger.warning(f"gate dropped nothing (입력 {len(kept)}건) — 판정력 확인 필요")
    for it in dropped:
        logger.info(f"  gate drop: {(it.get('title') or '')[:70]}")


def filter_foodtech_relevant(
    items: list[dict[str, Any]], client: httpx.Client | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """뉴스레터 조립용 2차 게이트 — (통과, 탈락) 반환.

    **`BATCH_SIZE`로 쪼개 호출한다** (T-028). 풀 전체를 한 번에 던지면 판정이 붕괴한다 —
    2026-08-17 실측으로 같은 풀 117건이 통짜 호출에선 drop 0건·심도 전부 3이었고,
    20건씩 쪼개니 drop 41건·심도 4/3/2로 갈렸다. 소배치에선 같은 프롬프트가 아파트 분양
    기사와 매체 첫 화면을 정확히 걸러낸다. 프롬프트가 아니라 **배치 크기가 판정력을 정한다**.

    키 없거나 게이트 응답이 아예 비면 보수적으로 전량 통과(발송 자체를 막지 않음).
    개별 항목에 keep=false가 명시되면 탈락시킨다(엄격한 프롬프트가 '애매하면 drop'을 책임).

    통과 항목에는 심도 판정을 `depth` 키로 얹어준다(T-024). **판정이 없으면 키를 안 넣는다** —
    호출부가 그걸 보고 기존 정렬로 되돌아간다. 원본 dict은 건드리지 않고 복사본을 돌려준다.
    """
    if not settings.openrouter_api_key or not items:
        return list(items), []
    if client is None:
        with httpx.Client() as own_client:
            return filter_foodtech_relevant(items, own_client)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for start in range(0, len(items), BATCH_SIZE):
        k, d = _gate_batch(items[start : start + BATCH_SIZE], client)
        kept += k
        dropped += d
    _log_gate_verdict(kept, dropped)
    return kept, dropped


def _parse_published_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def classify_and_store(
    items: list[dict[str, Any]],
    client: httpx.Client | None = None,
    session: Session | None = None,
) -> dict[str, int]:
    """신규 URL만 LLM 분류 → "해당없음" 폐기 → news_items에 멱등 저장.

    반환: {"new": 신규, "blocked": 도메인차단, "stored": 저장, "discarded": 폐기,
          "unclassified": 실패, "existing": 기존}
    """
    if not settings.openrouter_api_key:
        logger.warning("no OPENROUTER_API_KEY — classification skipped")
        return {
            "new": 0,
            "blocked": 0,
            "stored": 0,
            "discarded": 0,
            "unclassified": 0,
            "existing": 0,
        }
    if client is None:
        with httpx.Client() as own_client:
            return classify_and_store(items, client=own_client, session=session)
    if session is None:
        with Session(engine) as own_session:
            return classify_and_store(items, client=client, session=own_session)

    urls = [it["url"] for it in items if it.get("url")]
    existing = set(session.exec(select(NewsItem.url).where(col(NewsItem.url).in_(urls))).all())
    fresh = [it for it in items if it.get("url") and it["url"] not in existing]
    new_items = [it for it in fresh if not is_non_news_url(it["url"])]
    stats = {
        "new": len(fresh),
        "blocked": len(fresh) - len(new_items),
        "stored": 0,
        "discarded": 0,
        "unclassified": 0,
        "existing": len(existing),
    }
    if not new_items:
        return stats

    labels: dict[int, str] = {}
    for start in range(0, len(new_items), BATCH_SIZE):
        batch = new_items[start : start + BATCH_SIZE]
        payload = [
            # 수집 컷(300자)과 일치 — 200자였을 땐 Brave 요약 28/40건이 잘렸다(07-21 실측)
            {"id": start + i, "title": it["title"], "summary": (it.get("summary") or "")[:300]}
            for i, it in enumerate(batch)
        ]
        content = _call_openrouter(client, payload)
        batch_labels = _parse_labels(content)
        if not batch_labels:
            # 200인데 빈/깨진 응답 간헐 재현(07-21 배치 3개 유실) — 1회 재시도
            batch_labels = _parse_labels(_call_openrouter(client, payload))
        labels.update(batch_labels)

    now = datetime.now(UTC)
    for i, it in enumerate(new_items):
        label = labels.get(i)
        if label is None:
            stats["unclassified"] += 1
            continue
        if label == DISCARD_LABEL:
            stats["discarded"] += 1
            continue
        stmt = (
            pg_insert(NewsItem)
            .values(
                title=it["title"],
                url=it["url"],
                summary=(it.get("summary") or "")[:300],
                source=it.get("source") or "",
                origin=it.get("origin") or "",
                region=it.get("region") or "",
                category=SLUG_BY_KO[label],
                published_at=_parse_published_at(it.get("published_at")),
                collected_at=now,
            )
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(col(NewsItem.id))
        )
        if session.execute(stmt).scalar() is not None:
            stats["stored"] += 1
    session.commit()
    logger.info(f"news classified: {stats}")
    return stats
