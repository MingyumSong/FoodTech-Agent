"""T-004 뉴스 LLM 분류 드라이런.

data/news_cache.json의 수집 뉴스를 후보 모델 4개로 각각 10대 핵심분야 분류시키고
실측 비용·지연·파싱 실패율·모델 간 일치율을 산출한다. 일회성 리서치 스크립트.

실행: uv run python scripts/llm_dryrun.py
결과: data/llm_dryrun_results.json (data/는 gitignore 대상)
"""

import json
import re
import time
from itertools import combinations
from pathlib import Path

import httpx

from app.config import settings
from app.services.news import read_news_cache

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "anthropic/claude-haiku-4.5",
    "google/gemini-2.5-flash",
    "openai/gpt-5-mini",
    "google/gemini-2.5-flash-lite",
]

CATEGORIES = [
    "세포배양식품",
    "식물기반식품",
    "간편식",
    "식품프린팅",
    "스마트제조",
    "스마트유통",
    "커스터마이징",
    "외식 푸드테크",
    "업사이클링",
    "친환경포장",
    "해당없음",
]

SYSTEM_PROMPT = f"""당신은 푸드테크 뉴스 분류기다. 각 뉴스를 정부 "푸드테크 10대 핵심분야" 중
정확히 하나로 분류하라. 푸드테크와 무관한 뉴스는 "해당없음"으로 분류하라.

허용 카테고리 (이 목록의 문자열을 그대로 사용):
{json.dumps(CATEGORIES, ensure_ascii=False)}

출력은 JSON 배열만. 다른 텍스트·설명·코드펜스 금지:
[{{"id": 0, "category": "간편식"}}, ...]"""

BATCH_SIZE = 20
OUT_PATH = Path("data/llm_dryrun_results.json")


def call_model(client: httpx.Client, model: str, batch: list[dict]) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ],
        "max_tokens": 8000,
        "usage": {"include": True},
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    for attempt in range(3):
        resp = client.post(OPENROUTER_URL, json=payload, headers=headers, timeout=180)
        if resp.status_code in (429, 500, 502, 503):
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def parse_labels(text: str) -> dict[int, str]:
    """응답에서 JSON 배열을 관대하게 추출. 실패 항목은 누락시킨다."""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return {}
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    labels = {}
    for row in rows:
        if isinstance(row, dict) and row.get("category") in CATEGORIES and "id" in row:
            labels[int(row["id"])] = row["category"]
    return labels


def main() -> None:
    assert settings.openrouter_api_key, "OPENROUTER_API_KEY가 .env에 없다"
    cache = read_news_cache()
    assert cache and cache["items"], "뉴스 캐시가 비어 있다 — POST /jobs/news-refresh 먼저"

    items = [
        {"id": i, "title": it["title"], "summary": it["summary"][:200]}
        for i, it in enumerate(cache["items"])
    ]
    print(f"items: {len(items)}, models: {len(MODELS)}")

    results: dict[str, dict] = {}
    with httpx.Client() as client:
        for model in MODELS:
            labels: dict[int, str] = {}
            cost = 0.0
            elapsed = 0.0
            tokens_in = tokens_out = 0
            for start in range(0, len(items), BATCH_SIZE):
                batch = items[start : start + BATCH_SIZE]
                t0 = time.monotonic()
                data = call_model(client, model, batch)
                elapsed += time.monotonic() - t0
                usage = data.get("usage", {})
                cost += usage.get("cost", 0.0) or 0.0
                tokens_in += usage.get("prompt_tokens", 0)
                tokens_out += usage.get("completion_tokens", 0)
                content = data["choices"][0]["message"]["content"] or ""
                labels.update(parse_labels(content))
            missing = len(items) - len(labels)
            results[model] = {
                "labels": {str(k): v for k, v in labels.items()},
                "cost_usd": round(cost, 6),
                "elapsed_s": round(elapsed, 1),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "parse_missing": missing,
            }
            print(
                f"{model:38s} cost=${cost:.4f} elapsed={elapsed:.1f}s "
                f"missing={missing} out_tokens={tokens_out}"
            )

    # 모델 간 pairwise 일치율
    agreement = {}
    for a, b in combinations(MODELS, 2):
        la, lb = results[a]["labels"], results[b]["labels"]
        common = set(la) & set(lb)
        same = sum(1 for k in common if la[k] == lb[k])
        agreement[f"{a} vs {b}"] = round(same / len(common), 3) if common else None

    # 카테고리 분포
    distribution = {
        m: {c: list(r["labels"].values()).count(c) for c in CATEGORIES if c in r["labels"].values()}
        for m, r in results.items()
    }

    # 다수결 대비 불일치 샘플 (보고서용)
    disagreements = []
    for i, it in enumerate(items):
        votes = {m: results[m]["labels"].get(str(i)) for m in MODELS}
        values = [v for v in votes.values() if v]
        if len(set(values)) > 1:
            disagreements.append({"title": it["title"], "votes": votes})

    out = {
        "run_at": cache["updated_at"],
        "n_items": len(items),
        "models": results,
        "agreement": agreement,
        "distribution": distribution,
        "disagreements": disagreements,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {OUT_PATH}")
    print("agreement:", json.dumps(agreement, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
