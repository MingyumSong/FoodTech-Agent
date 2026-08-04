# T-022 refresh_pilot_stats 배치화 (N+1 제거)

Type: TASK
Status: TODO (2026-08-04 — 세션 랩 분석에서 발견, 코드로 확인함. **확대 발송 전에 처리**)

## Problem

- 현재 동작: `refresh_pilot_stats`가 회원 링크마다 루프 안에서 쿼리를 돈다 —
  `session.get(Member)` + `send_logs` 조회 + `engagement_events` 조회 + `PilotMember` 조회.
  **회원 1명당 4회, 25명이면 약 100회 원격 왕복.**
- 기대 동작: 필요한 데이터를 한 번에 가져와 메모리에서 조립한다.
- 왜 필요한가: DB가 Supabase(원격)라 왕복 지연이 그대로 쌓인다. 지금 25명은 견디지만
  **확대 발송 시 즉시 병목**이고, 이 잡은 매일 13:00 발송 경로 안에서 돈다(`run_pilot_daily`가
  발송 전후로 두 번 호출). 느려지면 크론이 타임아웃되고 발송 자체가 위태로워진다(C4).

  프로젝트 메모리에 **"원격 DB는 배치로 — 행당 쿼리 금지, 전체 로드+메모리 인덱스(10분→2.8초)"**가
  이미 적혀 있다. 같은 실수를 반복한 자리다.

## Context

- `app/services/pilot_daily.py` — `refresh_pilot_stats`. 루프 진입 전에 `news_cat`과
  `score_members`는 **이미 배치로** 가져온다(좋은 패턴이 같은 함수 안에 있다). 나머지 4곳만 남았다.
- `app/models/{member,send_log,engagement_event,pilot_member}.py` — 조회 대상.
- `engagement_events`에는 `ix_engagement_events_member_occurred`(member_id, occurred_at) 인덱스가 있다.

참고 사례: T-007 회원 임포터에서 같은 문제를 전체 로드 + 메모리 인덱스로 풀어 10분 → 2.8초가 됐다.

## Scope

허용: `refresh_pilot_stats` 내부 쿼리 구조 변경, 테스트.

금지:

- **집계 결과값 변경.** 이 티켓은 순수 성능 작업이다. 숫자가 하나라도 달라지면 실패다.
- 멱등성 훼손 — 재실행해도 같은 결과여야 한다(T-011 AC5).
- 스키마 변경.
- `score_members` 내부 최적화 — 별개 사안이면 별도 티켓.

## Acceptance Criteria

1. 회원 수에 비례해 쿼리가 늘지 않는다 — 루프 안에서 DB를 치지 않는다.
2. **집계 결과가 변경 전과 완전히 동일하다.** 같은 입력에 같은 출력.
3. 멱등 유지 — 두 번 돌려도 같은 값.
4. 회원 0명·이벤트 0건에서 예외 없이 동작한다.
5. 기존 테스트(`test_pilot_daily.py`의 롤업 검증)가 그대로 통과한다.

## Verification

1. `bash scripts/check.sh` exit=0.
2. **동일성 검증**: 운영 데이터 스냅샷으로 변경 전/후 `pilot_members` 전 컬럼을 비교해 차이 0건 확인.
3. 쿼리 수 측정(SQLAlchemy 이벤트 훅 등)으로 회원 수와 무관함을 보인다.
