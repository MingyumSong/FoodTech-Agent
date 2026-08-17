# T-028 2차 게이트 붕괴 — 통짜 배치가 판정력을 죽인다

Type: BUG
Status: DONE (2026-08-17 — AC 7/7 구현·배포. check.sh 그린.
**Verification 3(다음 발송 실물 검수)은 8/18 13:00 KST 발송 후 확인**)

## Problem

- **현재 동작**: `filter_foodtech_relevant`가 풀 전체(오늘 117건)를 LLM 한 번에 던진다.
  판정이 붕괴해 **drop 0건**, 심도는 전부 3 근처로 뭉친다. 심도가 평평하면 `_deep_first`는
  안정 정렬이라 입력 순서(=최신순)가 그대로 남고, T-024가 세운 "심도로 메인을 고른다"가 무효가 된다.
- **기대 동작**: 수집 분류(`classify_and_store`)와 같이 `BATCH_SIZE`(20)로 쪼개 판정한다.
- **왜 필요한가**: 실제로 무너진 게 배포돼 있다. 2026-08-17 푸디픽 #026의 다섯 꼭지 중
  **아파트 분양 기사가 메일 제목**이 됐고(`부경경마공원역 디에트르 더 리버`), 해외 1꼭지는
  기사가 아니라 매체 첫 화면(`https://thedieline.com/`)이었다. 칼럼·지자체 홍보도 함께 나갔다.

### 실측 (2026-08-17, 같은 풀 117건)

| 호출 방식 | keep | drop | 심도 분포 |
|---|---|---|---|
| 통짜 117건 (현재) | 117 | **0** | 사실상 전부 3 |
| 20건씩 청크 | 76 | **41** | 4:18 / 3:51 / 2:7 |
| 5건만 (격리 실험) | 2 | 3 | 아파트·DIELINE·인물인터뷰 전부 drop |

프롬프트는 멀쩡하다 — 소배치에선 같은 프롬프트가 정확히 걸러낸다. **배치 크기가 원인이다.**
같은 파일 27행에 `BATCH_SIZE = 20`이 이미 있고 수집 분류는 그걸로 쪼개 부른다. 게이트만 안 썼다.

부수 관측: 통짜 호출은 `temperature=0`인데도 두 번 실행에서 같은 기사가 d3→d4로 흔들렸다.
재현되지 않는 판정은 튜닝할 수 없다(T-024가 같은 이유로 temperature를 고정했다).

## Context

- `app/services/news_classify.py` — `filter_foodtech_relevant`(313행), `BATCH_SIZE`(27행),
  `is_non_news_url`(162행), `NON_NEWS_DOMAINS`(53행)
- `app/services/pilot_daily.py` — `_deep_first` / `select_picks`(게이트 결과를 쓰는 쪽)
- 재현 스크립트: 세션 스크래치패드 `gate_repro.py` / `gate_chunked.py` / `gate_small.py`

곁가지 두 건(같은 발송 품질 문제라 함께 처리):

- 기사가 아닌 URL이 통과한다 — `https://thedieline.com/`처럼 **경로 없는 매체 첫 화면**.
- 관측된 비기사 도메인(시장보고서 판매·주식 정보 사이트)이 차단 목록에 없다.

## Scope

허용:

- `app/services/news_classify.py` — 게이트 청크 분할, 판정 로깅, 루트 URL·도메인 차단
- `tests/test_news_classify.py` — 회귀 테스트
- `app/services/pilot_daily.py` + `app/routes/jobs.py` — 발송 결과 조회(조용한 실패 대응)
- `.github/workflows/{pilot-daily-send,news-refresh}.yml` — 트리거 재시도 + 결과 검증

금지:

- DB 스키마 변경 (게이트 판정 영구 기록은 후속 티켓)
- 게이트 프롬프트 문구 변경 — 이번 원인이 아니다. 배치만 고치고 효과를 먼저 본다
- Brave 엔드포인트 교체(web→news) — 측정이 필요해 회의 안건으로 분리

## Acceptance Criteria

1. 게이트가 `BATCH_SIZE`(20) 단위로 나눠 호출된다. 45건 입력 → 3회 호출.
2. 청크 하나가 실패해도 그 청크만 전량 통과하고 나머지 판정은 살아남는다.
3. 게이트 결과(청크별 keep/drop, 심도 분포, drop된 제목)가 로그에 남는다.
4. 경로·쿼리가 없는 루트 URL은 비기사로 차단된다.
5. `/jobs/pilot-daily-status`가 오늘 편의 실제 발송 여부를 답한다(JOBS_TOKEN 인증).
6. 크론이 트리거 수락이 아니라 **발송 결과**로 성공/실패를 판정한다. 트리거는 3회 재시도한다
   (2026-08-14 news-refresh 실패 원인 = Railway 일시 404 `Application not found`).
7. 기존 기능이 깨지지 않는다.

## Verification

1. `bash scripts/check.sh` 그린.
2. 운영 풀로 재현: 수정 후 `gate_repro.py`가 drop > 0, 심도가 2~4로 분포.
3. 배포 후 다음 발송(13:00 KST)에서 로그의 청크별 keep/drop 확인, 나간 편의 꼭지를 눈으로 검수.
4. `/jobs/pilot-daily-status` 200 + `ok: true` (발송일 기준).

## 결과 (2026-08-17 배포 후 운영 풀 재현)

| | 수정 전 | 수정 후 |
|---|---|---|
| 게이트 | keep 117 / **drop 0** | keep 85 / **drop 31** |
| 심도 분포 | 사실상 전부 3 | 4:20 / 3:52 / 2:11 / 1:2 |
| 오늘 나간 아파트 분양 기사 | 메인 1번·메일 제목 | **drop** |
| 매체 첫 화면(thedieline.com/) | 해외 1꼭지 | **풀 진입 전 차단** |
| [전문가 기고] 칼럼 | 에피타이저 | **drop** |

`/jobs/pilot-daily-status` 라이브 확인: 토큰 없이 401, 토큰으로
`{"ok":true,"status":"sent","sent":24}`.

남은 것(이 티켓 밖):

- 게이트 판정을 DB에 영구 기록 — 지금은 로그가 유일한 기록이고 로그는 흘러간다.
- Brave 엔드포인트 web→news 교체 검토. 뉴스 검색도 주식 스팸·부고가 섞여 측정이 필요하다.
- 해외 풀 자체가 얇다(7일 13건). 소스 보강은 별건.
