# T-021 반응 버튼 봇 클릭 필터

Type: BUG
Status: CLOSED — 문제 없음 (2026-08-18 — **관측 결과 봇 반응이 실재하지 않는다.** 아래 실측 참조)

## 관측 결과 (2026-08-18, 운영 DB 읽기 전용)

이 티켓이 스스로 요구한 "필터부터 만들지 말고 관측이 먼저다"를 실행한 결과다.

```sql
SELECT COUNT(*) reacted,
       COUNT(*) FILTER (WHERE e.occurred_at - s.created_at < interval '10 seconds') within_10s,
       COUNT(*) FILTER (WHERE e.occurred_at - s.created_at < interval '60 seconds') within_60s,
       ROUND(MIN(EXTRACT(EPOCH FROM (e.occurred_at - s.created_at)))) min_delay_sec
FROM engagement_events e
JOIN send_logs s ON s.newsletter_id = e.newsletter_id AND s.member_id = e.member_id
WHERE e.event_type = 'reacted';
```

| reacted | within_10s | within_60s | min_delay_sec |
| --- | --- | --- | --- |
| 14 | **0** | **0** | **267** |

회원 7명, 2026-08-05~08-15(첫 실사용부터 11일). **가장 빠른 반응이 발송 4분 27초 뒤**로,
프리페치라면 나올 수 없는 지연이다. 열람(`BOT_OPEN_SECONDS = 10`)과 달리 반응에는 방어가
없어도 됐다 — 클릭 한 번이 더 필요한 경로라 링크 훑기 봇이 안 누르는 것으로 보인다.

**따라서 필터를 만들지 않는다.** 있지도 않은 문제를 막느라 진짜 반응을 버리는 게 더 나쁘다
(이 티켓의 원래 판단이 옳았다). Activity Score 상위 랭킹은 봇으로 오염되지 않았다.

**되살릴 조건**: 발송이 파일럿 25명을 넘어 확대되면 수신자의 메일 클라이언트 구성이 달라진다.
확대 발송 후 위 쿼리를 다시 돌려 `within_10s > 0` 이면 이 티켓을 다시 연다.

---

<details>
<summary>원래 티켓 내용 (관측 전 가설)</summary>

## Problem

- 현재 동작: 디저트 반응 링크(T-013)는 인증 없는 **GET**이다. 메일 클라이언트나 보안 게이트웨이가
  링크를 미리 훑으면(prefetch) 사람이 안 눌러도 반응이 기록된다. `app/routes/reactions.py`에
  시간 기반 필터가 없다(확인함).
- 기대 동작: 발송 직후 기계적으로 눌린 반응은 점수에 반영되지 않는다.
- 왜 필요한가: **T-017의 최고 가중치가 여기 걸려 있다.** `W_REACTED = 5.0`으로 열람(1.0)·클릭(3.0)보다
  높다. 봇이 대신 누르면 전원이 "좋았어요"가 되고 **Activity Score 상위 랭킹이 통째로 무의미해진다.**
  결정 5가 열람을 보조 신호로 낮춘 것과 같은 이유가 반응에도 적용된다.

  T-017은 열람에 `BOT_OPEN_SECONDS = 10` 필터를 뒀는데 **반응에는 같은 방어가 없다.**
  CLAUDE.md 결정 11에도 "Outlook Safe Links 봇 클릭은 T-003 추적 정확도 전체에 영향"이라고 적혀 있다.

  단, 반응 버튼은 **2026-08-05 13:00 발송이 첫 실사용**이다. 실제로 봇 클릭이 오는지 확인하기 전에
  필터부터 만들면 있지도 않은 문제를 막느라 진짜 반응을 버릴 수 있다. **관측이 먼저다.**

## Context

- `app/routes/reactions.py` — 공개 GET 라우트. 주석에 프리페치 위험을 이미 적어뒀지만
  "멱등이라 통계가 부풀지 않는다"까지만 방어했다. **값이 틀리는 건 못 막는다.**
- `app/services/engagement.py` — `record_reaction`(멱등 키 = 회원×편, 마지막 값으로 수렴).
- `app/services/activity_score.py` — `W_REACTED`, `BOT_OPEN_SECONDS`(열람용 기존 필터 — 같은 패턴 참고).
- `app/models/send_log.py` — 발송 시각. "발송 후 몇 초"를 재려면 이게 기준이다.

## Scope

허용: 반응 적재 시 봇 판정, `activity_score`에서 봇 반응 제외, 관리자 화면에 봇 추정 건수 표시, 테스트.

금지:

- 반응 링크를 POST로 바꾸기 — 이메일에서 POST는 안 눌린다.
- 원본 이벤트 삭제 — 봇으로 판정해도 기록은 남기고 **점수에서만** 뺀다(T-017이 열람에 쓴 방식).
- 자바스크립트 확인 단계 추가 — 클릭 한 번이라는 가치를 깨뜨린다.

## Acceptance Criteria

1. **선행: 첫 실데이터에서 봇 패턴이 실재하는지 확인한다.** 발송 시각 대비 반응 시각 분포를 보고,
   수 초 내에 몰려 있으면 봇이다. 없으면 이 티켓은 닫고 관측만 계속한다.
2. (봇이 확인될 경우) 발송 후 일정 시간 안의 반응은 점수 계산에서 제외한다. 임계값과 근거를 주석에 남긴다.
3. 봇 판정된 반응도 `engagement_events`에는 남는다 — 판정 기준이 틀렸을 때 되돌릴 수 있어야 한다.
4. 같은 회원이 같은 편에 여러 반응을 남겨도 1행 수렴은 유지된다(T-013 AC7).
5. 봇 추정 건수가 화면이나 로그에 드러난다.

## Verification

1. **2026-08-05 13:00 발송분**: `send_logs.created_at`과 `engagement_events.occurred_at`(reacted)의
   차이 분포를 뽑아본다. 25명 중 몇 명이 몇 초 만에 반응했는지.
2. `bash scripts/check.sh` exit=0.
3. 단위 테스트: 발송 직후 반응 / 한참 뒤 반응 / 반응 없음 각각의 점수 반영.

</details>
