import json

import pytest
from sqlmodel import Session, select

from app.config import settings
from app.models.news_item import NewsItem
from app.services import news_classify
from app.services.news_classify import SLUG_BY_KO, _parse_labels, classify_and_store


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")


def _item(url: str, title: str = "제목") -> dict:
    return {
        "title": title,
        "url": url,
        "summary": "요약",
        "source": "테스트일보",
        "origin": "naver",
        "region": "domestic",
        "published_at": "2026-07-18T09:00:00+00:00",
    }


def _fake_llm(labels_by_id: dict[int, str]):
    """_call_openrouter 대체 — 배치의 id에 맞춰 지정된 라벨을 돌려준다."""

    def fake(client, batch):
        rows = [
            {"id": row["id"], "category": labels_by_id[row["id"]]}
            for row in batch
            if row["id"] in labels_by_id
        ]
        return json.dumps(rows, ensure_ascii=False)

    return fake


def test_stores_slug_and_discards_irrelevant(session: Session, monkeypatch):
    monkeypatch.setattr(
        news_classify,
        "_call_openrouter",
        _fake_llm({0: "세포배양식품", 1: "해당없음", 2: "일반"}),
    )
    items = [_item("https://a.com/1"), _item("https://a.com/2"), _item("https://a.com/3")]
    stats = classify_and_store(items, client=object(), session=session)  # pyright: ignore[reportArgumentType]

    assert stats == {
        "new": 3,
        "blocked": 0,
        "stored": 2,
        "discarded": 1,
        "unclassified": 0,
        "existing": 0,
    }
    rows = list(session.exec(select(NewsItem).order_by(NewsItem.id)).all())  # pyright: ignore[reportArgumentType]
    assert [r.category for r in rows] == ["cell_cultured", "general"]
    assert rows[0].url == "https://a.com/1"
    assert rows[0].published_at is not None


def test_existing_urls_skip_llm_call(session: Session, monkeypatch):
    calls = {"n": 0}

    def counting_llm(client, batch):
        calls["n"] += 1
        return json.dumps([{"id": row["id"], "category": "간편식"} for row in batch])

    monkeypatch.setattr(news_classify, "_call_openrouter", counting_llm)
    items = [_item("https://a.com/1")]
    classify_and_store(items, client=object(), session=session)  # pyright: ignore[reportArgumentType]
    assert calls["n"] == 1

    # 같은 URL 재실행 — LLM 호출 없이 existing으로 스킵 (멱등 + 비용 절약)
    stats = classify_and_store(items, client=object(), session=session)  # pyright: ignore[reportArgumentType]
    assert calls["n"] == 1
    assert stats["new"] == 0 and stats["existing"] == 1
    assert len(list(session.exec(select(NewsItem)).all())) == 1


def test_empty_response_retried_once_per_batch(session: Session, monkeypatch):
    """200인데 빈/깨진 응답이 오면 그 배치만 1회 재시도한다 (07-21 운영 1차 배치 유실 재발 방지)."""
    calls = {"n": 0}

    def flaky_llm(client, batch):
        calls["n"] += 1
        if calls["n"] == 1:
            return ""  # 첫 호출은 빈 응답
        return json.dumps([{"id": row["id"], "category": "간편식"} for row in batch])

    monkeypatch.setattr(news_classify, "_call_openrouter", flaky_llm)
    stats = classify_and_store(
        [_item("https://a.com/1")],
        client=object(),  # pyright: ignore[reportArgumentType]
        session=session,
    )
    assert calls["n"] == 2
    assert stats["stored"] == 1 and stats["unclassified"] == 0


def test_parse_failure_leaves_item_for_retry(session: Session, monkeypatch):
    monkeypatch.setattr(news_classify, "_call_openrouter", lambda c, b: "널 위한 답은 없다")
    stats = classify_and_store(
        [_item("https://a.com/1")],
        client=object(),  # pyright: ignore[reportArgumentType]
        session=session,
    )
    assert stats["unclassified"] == 1 and stats["stored"] == 0
    assert list(session.exec(select(NewsItem)).all()) == []


def test_no_api_key_skips_everything(session: Session, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    stats = classify_and_store([_item("https://a.com/1")], session=session)
    assert stats == {
        "new": 0,
        "blocked": 0,
        "stored": 0,
        "discarded": 0,
        "unclassified": 0,
        "existing": 0,
    }


def test_non_news_domains_blocked_before_llm(session: Session, monkeypatch):
    """위키백과·시세 페이지는 LLM에 보내지 않고 결정적으로 차단한다 (2026-07-21 검수 반영)."""
    calls = {"n": 0}

    def counting_llm(client, batch):
        calls["n"] += 1
        return json.dumps([{"id": row["id"], "category": "간편식"} for row in batch])

    monkeypatch.setattr(news_classify, "_call_openrouter", counting_llm)
    items = [
        _item("https://en.wikipedia.org/wiki/3D_printing"),
        _item("https://finance.yahoo.com/quote/RR/"),
        _item("https://a.com/1"),
    ]
    stats = classify_and_store(items, client=object(), session=session)  # pyright: ignore[reportArgumentType]

    assert stats["new"] == 3 and stats["blocked"] == 2 and stats["stored"] == 1
    urls = [r.url for r in session.exec(select(NewsItem)).all()]
    assert urls == ["https://a.com/1"]
    assert calls["n"] == 1  # 차단분은 LLM 배치에 포함되지 않는다


def test_parse_labels_is_lenient():
    text = '설명이 붙어도 [{"id": 0, "category": "간편식"}, {"id": 1, "category": "없는분류"}] 추출'
    assert _parse_labels(text) == {0: "간편식"}
    assert _parse_labels("json 없음") == {}


def test_slug_mapping_covers_ten_categories_plus_general():
    assert len(SLUG_BY_KO) == 11
    assert "해당없음" not in SLUG_BY_KO
    assert len(set(SLUG_BY_KO.values())) == 11


def _fake_gate(keep_by_id: dict[int, bool]):
    """_call_openrouter 대체 — 게이트 keep 판정 JSON을 돌려준다 (system kwarg 허용)."""

    def fake(client, batch, system=None):
        rows = [{"id": r["id"], "keep": keep_by_id.get(r["id"], True)} for r in batch]
        return json.dumps(rows, ensure_ascii=False)

    return fake


def test_relevance_gate_drops_only_flagged(monkeypatch):
    monkeypatch.setattr(news_classify, "_call_openrouter", _fake_gate({0: True, 1: False, 2: True}))
    items = [
        _item("u0", "식품 3D프린팅 시장"),
        _item("u1", "추천 리스트클"),
        _item("u2", "식품공장 AI"),
    ]
    kept, dropped = news_classify.filter_foodtech_relevant(items)  # client=None → 목이 가로챔
    assert [it["url"] for it in kept] == ["u0", "u2"]
    assert [it["url"] for it in dropped] == ["u1"]


def test_relevance_gate_attaches_depth(monkeypatch):
    """심도 판정이 통과 항목에 실려 나온다 (T-024) — 메인/에피타이저를 가르는 근거."""

    def fake(client, batch, system=None):
        return json.dumps(
            [
                {"id": 0, "keep": True, "depth": 5},
                {"id": 1, "keep": True, "depth": 2},
            ]
        )

    monkeypatch.setattr(news_classify, "_call_openrouter", fake)
    kept, _ = news_classify.filter_foodtech_relevant([_item("u0"), _item("u1")])
    assert [it["depth"] for it in kept] == [5, 2]


def test_relevance_gate_ignores_bogus_depth(monkeypatch):
    """범위 밖 depth는 '판정 없음'으로 떨어뜨린다 — 최저점으로 때우면 안 된다.

    호출부(`_deep_first`)가 '판정 없음'을 보고 기존 정렬로 되돌아가기 때문이다.
    """

    def fake(client, batch, system=None):
        return json.dumps([{"id": 0, "keep": True, "depth": 9}])

    monkeypatch.setattr(news_classify, "_call_openrouter", fake)
    kept, _ = news_classify.filter_foodtech_relevant([_item("u0")])
    assert "depth" not in kept[0]


def test_relevance_gate_no_key_passes_all(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    items = [_item("u0"), _item("u1")]
    assert news_classify.filter_foodtech_relevant(items) == (items, [])


def test_relevance_gate_empty_response_passes_all(monkeypatch):
    # 게이트 응답이 두 번 다 비면 보수적으로 전량 통과(빈 뉴스레터 방지)
    monkeypatch.setattr(news_classify, "_call_openrouter", lambda c, b, system=None: "판정 없음")
    items = [_item("u0"), _item("u1")]
    kept, dropped = news_classify.filter_foodtech_relevant(items)  # client=None → 목이 가로챔
    assert kept == items and dropped == []
