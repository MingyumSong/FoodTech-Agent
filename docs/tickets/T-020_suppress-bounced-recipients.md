# T-020 반송·불만 회원 발송 억제

Type: BUG
Status: TODO (2026-08-04 — 세션 랩 분석에서 발견, 코드로 확인함)

## Problem

- 현재 동작: `_recipients`가 `subscribed`·이메일 보유만 거른다(`newsletter.py`).
  `engagement_events`에 `bounced`/`complained`가 적재되고 있는데도(`engagement.py`의
  `RESEND_EVENT_TYPES`) **수신자 목록에서 빠지지 않는다.** 반송된 주소로 계속 재발송된다.
- 기대 동작: 하드 바운스·스팸 신고 이력이 있는 주소는 발송 대상에서 자동으로 빠진다.
- 왜 필요한가: **두 가지가 동시에 망가진다.**
  ① **발신 도메인 평판** — 파일럿 25명에선 무해하지만 회원 3,413명으로 넓히면 반송률이 누적돼
     `news.foodtech-center.org`의 평판이 깎인다. 결정 8이 발송 전용 서브도메인을 따로 둔 이유가
     바로 평판 보호인데, 그 전제가 무너진다.
  ② **Activity Score 오염** — 도달 불가 회원이 "발송했는데 반응 없음"으로 계산돼 `dormant`가 된다.
     **도달 불가는 무관심이 아니다.** 분류의 목적이 "참여율 높은 회원 선별"인데 잘못 섞인다.

지금 당장 터지진 않는다. 확대 발송(본 발송) 전에 반드시 처리해야 하는 항목이다.

## Context

- `app/services/newsletter.py` — `_recipients(session, program)`가 수신자 선정의 단일 지점.
  `send_newsletter`가 이걸 호출하고 100명 가드도 이 결과로 잰다.
- `app/services/engagement.py` — `RESEND_EVENT_TYPES`에 `email.bounced`→`bounced`,
  `email.complained`→`complained`가 이미 매핑돼 적재 중이다. **데이터는 이미 있다.**
- `app/models/engagement_event.py` — `member_id`, `event_type`, `payload`(반송 사유가 들어있을 수 있음).
- `app/models/member.py` — `subscribed` 플래그. 억제를 여기에 반영할지 조회 시점에 거를지는 설계 결정.

설계 시 갈리는 점: **하드 바운스와 소프트 바운스를 구분할 것인가.** 일시적 실패(메일함 가득)까지
영구 제외하면 멀쩡한 회원을 잃는다. Resend payload의 bounce type을 봐야 한다.

## Scope

허용: `newsletter.py`의 수신자 조회, 억제 판단 서비스 함수, 관리자 화면에 억제된 회원 수 표시, 테스트.

금지:

- `engagement_events` 원본 삭제·수정 — 이벤트는 보존한다.
- 100명 가드(`PILOT_MAX_RECIPIENTS`) 변경 — 결정 4.
- 회원 레코드 삭제. 억제는 발송 제외이지 탈퇴가 아니다.
- 회원 PII를 로그에 남기기(C6).

## Acceptance Criteria

1. 하드 바운스 이력이 있는 주소는 수신자 목록에서 빠진다.
2. 스팸 신고(`complained`) 이력이 있는 주소도 빠진다 — 재발송은 법적으로도 위험하다.
3. 소프트 바운스(일시적)와 하드 바운스를 구분한다. 구분 근거를 코드 주석에 남긴다.
4. 억제된 회원이 몇 명인지 관리자 화면이나 로그(PII 없이)로 드러난다 — 조용히 줄어들면 안 된다.
5. Activity Score 계산에서 도달 불가 회원이 `dormant`로 잡히지 않는다(별도 등급이나 제외).
6. 기존 기능이 깨지지 않는다 — 파일럿 25명 발송이 그대로 동작한다.

## Verification

1. `bash scripts/check.sh` exit=0.
2. 단위 테스트: 하드 바운스 / 소프트 바운스 / 불만 / 정상 회원 각각의 포함·제외.
3. 운영 데이터로 현재 몇 명이 억제 대상인지 조회(발송 없이 조회만).
