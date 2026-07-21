# T-006: 뉴스 LLM 분류 통합 + DB 이관

Status: IN PROGRESS (2026-07-21 — HOLD 해제. 희정 검수 수령: `docs/research/뉴스분류_검수완료.md`,
78건 중 25건 지적 → 반영 완료: ① 프롬프트를 판정 순서 5단계로 보정(비뉴스·비푸드테크 폐기 강화,
행사·정책·기업 일반 소식은 "일반") ② 위키백과·야후 시세는 LLM 전 도메인 차단(`NON_NEWS_DOMAINS`)
③ 로컬 news_items 검수 반영(삭제 19·general 재분류 6 → 59건). **남은 것: AC7 배포**(railway up).
중복 기사 병합(같은 내용 2매체)은 발송 조립 단계(T-008)에서 처리 — 저장은 URL 단위 유지.)
※ 운영 노트: "해당없음" 폐기분은 DB에 없어 다음 크론에서 재분류됨 — 건당 비용 ~0이라 허용.

## Problem

매일 크론이 뉴스를 수집하지만 ① 분류 없이 ② 컨테이너 로컬 JSON 파일에만 쌓인다.
파일 캐시는 재배포 시 소실되고 이력이 안 남으며, Supabase의 클릭 이벤트(T-003)와
조인할 수 없다. 원래 그림 3번("수집 시 분류해서 DB에 저장")을 완성한다.

## Context

- 분류 모델 확정(T-004): `google/gemini-2.5-flash`, 한국어 라벨 프롬프트로 일치율 0.917 실측.
  프롬프트·배치(20건)·관대한 JSON 파싱은 `scripts/llm_dryrun.py`에서 재사용.
- 분류 시점 = 수집 시(결정 7). 발송 직전 실시간 분류 금지.
- 캐시 아이템의 `category`는 검색어 분야(수집 메타)로 LLM 분류와 다른 개념 — DB에선
  LLM 분류만 `category`로 저장한다.

### 설계 결정 (2026-07-18, 민겸 컨펌)

1. **저장 라벨 = 영문 슬러그, 표시 = 한국어, LLM I/O = 검증된 한국어 프롬프트 유지.**
   슬러그: cell_cultured/plant_based/convenience/food_printing/smart_manufacturing/
   smart_distribution/customizing/food_service/upcycling/eco_packaging/general.
2. **MECE 보완**: (ME) 기사당 라벨 1개, "가장 핵심 주제" 규칙 — 드라이런 91.7% 일치로 실무 충분.
   (CE) **`general`(일반 푸드테크) 버킷 신설** — 10대 분야 밖이지만 푸드테크인 기사
   (스마트팜·정밀발효·투자/정책 일반) 유실 방지. "해당없음"(무관)은 저장하지 않고 폐기(건수만 로그).
   정부 10대 체계(결정 2)는 유지 — general은 운영용 추가 버킷.
3. **실패 격리**: LLM 분류 실패는 수집을 막지 않는다(캐시·헬스체크 무관). 분류 실패분은
   저장하지 않고 다음 크론에서 재시도(URL이 DB에 없으므로 자동 재분류).
4. **멱등**: `news_items.url` UNIQUE + ON CONFLICT DO NOTHING. 이미 저장된 URL은
   분류 호출 자체를 건너뛰어 LLM 비용을 아낀다(신규 URL만 분류).

## Scope

- `docs/tickets/T-006_news-classify-db.md` (이 파일)
- `app/models/news_item.py` (신설) + `app/models/__init__.py`
- Alembic 마이그레이션 (news_items + RLS)
- `app/services/news_classify.py` (신설) — 분류·저장 서비스
- `app/services/news.py` — refresh 말미에 분류·저장 호출(실패 격리)
- `app/config.py`, `.env.example` — 분류 모델 설정
- `tests/test_news_classify.py` (신설)
- Scope 밖: 파일 캐시 폐기(헬스체크 의존 유지), 학술(OpenAlex) 수집, 발송 조회 API

## Acceptance Criteria

- [x] AC1: `news_items` 테이블 생성(url UNIQUE, category 인덱스, RLS 활성화) — 리비전 61c5f308e719
- [x] AC2: 분류 서비스가 신규 URL만 배치 분류 → "해당없음" 제외하고 슬러그로 저장,
      기존 URL은 LLM 호출 없이 스킵 ✅ 라이브 2차 실행: existing=75, LLM 호출 0
- [x] AC3: 같은 입력 재실행 → 중복 행 없음(멱등) ✅ url ON CONFLICT + 사전 스킵
- [x] AC4: LLM 오류/파싱 실패 시 수집·캐시는 정상 완료, 실패분은 미저장(다음 크론 재시도)
- [x] AC5: `refresh_news_cache()` 실행 시 분류·저장까지 한 번에 수행 (크론 변경 불필요)
      ✅ 라이브: 80건 수집 → 75 저장(11개 슬러그 전부 등장, general=11)·5 폐기·실패 0, 13초
- [x] AC6: `bash scripts/check.sh` 통과 ✅ 50 passed
- [ ] AC7 (라이브): 배포 후 `/jobs/news-refresh` → Supabase `news_items`에 분류된 행 적재 확인,
      "해당없음" 폐기 건수 로그 확인

## Verification

```bash
uv run alembic upgrade head
bash scripts/check.sh
# 로컬 라이브: OPENROUTER_API_KEY 있는 상태에서
uv run python -c "from app.services.news import refresh_news_cache; print(refresh_news_cache())"
# → 로컬 DB news_items 조회로 슬러그 분포 확인
# 배포 라이브(AC7): railway up → /jobs/news-refresh → Supabase Table Editor에서 news_items 확인
```
