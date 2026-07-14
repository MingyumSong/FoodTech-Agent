# T-004 뉴스 LLM 분류 드라이런 — 모델·비용 확정 (결정 7 후속)

Type: RESEARCH
Status: DONE (2026-07-14 — AC 4/4 충족. 4모델 × 80건 완주, 파싱실패 0, 총 실비 $0.045.
추천: google/gemini-2.5-flash 주력 (일치율 평균 0.917, $0.0077/80건, 16s).
gpt-5-mini는 지연(121s), flash-lite는 "해당없음" 미사용 결함으로 제외.
보고서: docs/research/llm-classification-dryrun.md)

## Problem

- 뉴스레터 큐레이션을 위해 수집 뉴스를 정부 "푸드테크 10대 핵심분야"로 자동 분류해야 한다 (CLAUDE.md 결정 2).
- LLM 호출은 OpenRouter 게이트웨이로 확정(결정 7)됐으나 **어떤 모델을 쓸지, 주간 비용이 얼마일지 미정**.
- T-001 완료로 실데이터(data/news_cache.json, 80건)가 생겼으므로 실측 비교가 가능해졌다.

## Context

- 후보 (OpenRouter 실시간 가격, 2026-07-14 조회):
  | 모델 | 입력/출력 $/M | 역할 |
  |---|---|---|
  | anthropic/claude-haiku-4.5 | 1.00 / 5.00 | 품질 기준점 |
  | google/gemini-2.5-flash | 0.30 / 2.50 | 저가 주력 후보 |
  | openai/gpt-5-mini | 0.25 / 2.00 | 저가 주력 후보 |
  | google/gemini-2.5-flash-lite | 0.10 / 0.40 | 최저가 도전 |
- 분류 체계: 10대 분야 + "해당없음" (수집 노이즈 걸러내기용).
- 키: `.env`의 OPENROUTER_API_KEY (한도 $25 설정됨).

## Scope

허용: `scripts/llm_dryrun.py`(일회성 스크립트), `app/config.py`에 openrouter_api_key 추가,
`.env.example` 갱신, `docs/research/llm-classification-dryrun.md`(결과 보고서).

금지: 수집 파이프라인(app/services/news.py)에 분류 로직 통합(별도 티켓),
DB 스키마 작업, 프롬프트 외 LLM 기능 실험.

## Acceptance Criteria

1. 4개 모델이 동일한 80건·동일 프롬프트로 분류를 완료한다.
2. 모델별 실측 비용(OpenRouter usage 기준)·지연·파싱 실패율이 기록된다.
3. 모델 간 일치율(pairwise agreement)이 산출된다.
4. 주간 운영 비용 추정(주 1회 × 수집량 기준)과 모델 추천이 보고서에 담긴다.

## Verification

1. `uv run python scripts/llm_dryrun.py` 실행 → 스크래치 결과 JSON 생성.
2. 보고서의 수치가 결과 JSON과 일치.
3. OpenRouter 대시보드 크레딧 차감이 추정 비용과 자릿수 일치.
