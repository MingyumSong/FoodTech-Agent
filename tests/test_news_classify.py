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
