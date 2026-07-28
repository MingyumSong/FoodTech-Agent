# T-011 파일럿 매일발송 자동화

Type: FEAT
Status: DONE

## Problem

- 현재 동작: 파일럿(랩실 25명) 발송이 scratchpad 스크립트(`build_today.py` 조립 → `send_today.py`
  발송 → `backfill_pilot.py` 롤업)로 **손수** 돈다. 세션마다 사람이 3개 스크립트를 순서대로 실행해야 함.
- 기대 동작: GitHub Actions 크론이 매일 앱의 `/jobs/pilot-daily-send`를 때리면 조립·발송·통계 롤업이
  자동으로 끝난다. 사람이 개입하지 않아도 파일럿 실데이터가 매일 누적된다.
- 왜 필요한가: 로드맵 항목 3. 파일럿 발송이 수동이라 매일 돌리기 어렵고, Activity Score 가중치를
  확정할 실데이터(열람·클릭) 누적이 사람 손에 묶여 있다. 자동화해야 5·6·7주차 데이터가 쌓인다.

## Context

승격 대상 scratchpad 로직 (참고 전용, 앱 컨벤션으로 재작성):
- `build_today.py` — 게이트(`filter_foodtech_relevant`) + 논문/비푸드테크 제거 + 국내3:해외2 + 분야 distinct.
- `send_today.py` — `pilot-daily` 세그먼트로 Newsletter 생성/재사용 → `send_newsletter` 발송(멱등).
- `backfill_pilot.py` — send_logs·engagement_events → `pilot_members` 롤업(발송·열람·클릭·분야별 클릭).

재사용할 앱 코드:
- `app/services/newsletter.py`: `send_newsletter`(멱등·100가드·provider_id), `_recipients`,
  `_recent_items`, `_item_dict`, `UNSUB_PLACEHOLDER`, `render_foodie_pick`.
- `app/services/news_classify.py`: `filter_foodtech_relevant(items, client) -> (kept, dropped)`,
  `SLUG_BY_KO`(분야 슬러그 10종 + general).
- `app/models/pilot_member.py`: `PilotMember`(member_id 유니크, 발송·추적 집계 + category_clicks/opens).
- `app/routes/jobs.py`: `require_jobs_token`, BackgroundTasks 패턴(C4).

수신자: 25명은 이미 Supabase에서 `pilot-daily` 프로그램에 링크됨(#906 발송 때 임포트). 앱은 명단(PII)을
레포에 두지 않고 member_programs에서 조회한다.

## Scope

허용:
- `app/services/pilot_daily.py` 신규: 조립(게이트+분야 회전+3:2)·`run_pilot_daily`·`refresh_pilot_stats`.
- `app/routes/jobs.py`에 `POST /jobs/pilot-daily-send` 추가.
- `.github/workflows/pilot-daily-send.yml` 신규(매일 KST 크론, 시크릿 APP_URL·JOBS_TOKEN 재사용).
- `tests/test_pilot_daily.py` 신규.

금지:
- DB 스키마 변경(pilot_members는 T-011 이전에 이미 생성됨 — 컬럼 그대로 사용).
- `send_newsletter`/`build_newsletter` 등 기존 발송 로직 수정(재사용만).
- 명단·이메일 등 PII를 레포/로그에 남기기.
- archive/ 수정(C5), Supabase 특화 기능(C3).

## Acceptance Criteria

1. `POST /jobs/pilot-daily-send`(Bearer JOBS_TOKEN)가 즉시 202/accepted 응답하고,
   백그라운드에서 조립→발송→롤업을 수행한다(C4: 즉시 응답, 잡 본체는 서비스 함수).
2. 조립은 **전원 동일 1편**이며, 게이트 통과분에서 국내3:해외2 + 분야 distinct로 5꼭지를 고른다.
3. **일별 분야 회전**: 날짜에 따라 우선 분야가 회전해, 연속 2일이면 서로 다른 분야 집합이 노출된다
   (콜드스타트 다양성). 같은 날 재호출은 같은 편을 재사용(멱등).
4. 발송은 `send_newsletter` 재사용 — 멱등(이미 sent 스킵)·100명 가드·provider_id 저장.
5. `refresh_pilot_stats`가 send_logs·engagement_events를 `pilot_members`로 멱등 롤업한다
   (emails_sent/opened/links_clicked/last_*_at/category_clicks).
6. 뉴스가 최소 꼭지 수(5)에 못 미치면 발송하지 않고 명확히 실패 신호를 남긴다.
7. 기존 기능이 깨지지 않는다(기존 /jobs/* 무변경, check.sh 그린).

## Verification

1. `uv run pytest tests/test_pilot_daily.py -q` — 회전(2일 분야집합 상이)·다양성(분야 중복 없음)·
   롤업(집계 정확)·부족분 방어 통과.
2. `bash scripts/check.sh` — ruff + pyright + 전체 pytest 그린.
3. (운영, 배포 후) `curl -X POST $APP_URL/jobs/pilot-daily-send -H "Authorization: Bearer $JOBS_TOKEN"`
   → accepted → 로그에 조립/발송/롤업 흔적, pilot_members emails_sent 증가 확인.
