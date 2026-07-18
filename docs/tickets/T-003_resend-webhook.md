# T-003: Resend 웹훅 수신 — 참여 이벤트 적재

Status: DONE (2026-07-18 — AC 8/8 충족. 라이브 검증: 테스트 메일 2통 → delivered×2/opened/clicked×2가
Supabase에 적재, clicked url=원본 기사 URL(캐시 매칭 설계 성립). 추적 도메인 links.news.foodtech-center.org
Verified(Cloudflare CNAME, DNS only). 산출물: app/routes/webhooks.py, app/services/engagement.py, app/lib/webhook.py)

## Problem

"추적 → 점수 → 분류"의 원천 데이터가 없다. Resend가 보내주는 open/click/bounce 이벤트를
받아 `engagement_events`에 적재해야 Activity Score(T-00x)가 가능하다. 공개 URL(T-005)이
생겨 이제 수신할 수 있다.

## Context

- 스키마는 T-002에서 준비됨 — 마이그레이션 불필요:
  - `engagement_events`: `provider_event_id` UNIQUE(멱등), `payload` JSONB(원본 보존),
    member/newsletter/send_log FK 비정규화(수신 시점 해석).
  - `send_logs.provider_id` = Resend `email_id` → 이벤트를 회원·캠페인으로 역추적하는 조인 키.
- Resend 웹훅은 svix 서명(`svix-id`/`svix-timestamp`/`svix-signature` 헤더, HMAC-SHA256).
  서명 검증이 곧 인증 — Bearer 토큰 없음. 시크릿은 Resend 대시보드에서 웹훅 생성 시 발급(`whsec_...`).
- 재시도 정책: 비 2xx 응답이면 svix가 같은 `svix-id`로 재전송 → `provider_event_id`=svix-id로 멱등.

### 설계 결정 (CLAUDE.md 결정 3의 후속 3건)

1. **Google News 링크 디코딩 안 함.** 뉴스레터 링크는 우리 캐시의 URL을 그대로 쓰므로,
   클릭 URL == 캐시 item URL **문자열 그대로 매칭**으로 뉴스별 집계 가능. 원본은 payload JSONB에 보존.
2. **Safe Links 봇 클릭 방어는 적재 단계가 아니라 Score 계산 단계에서.** 적재는 전부 저장
   (click의 userAgent·ipAddress가 payload에 남음), 봇 필터링(발송 직후 수 초 내 클릭·MS UA 등)은
   Score 티켓에서 규칙화. 원본을 버리지 않아야 규칙을 나중에 바꿀 수 있다.
3. **이벤트 허용 목록**: delivered / opened / clicked / bounced / complained만 적재.
   `email.sent`는 send_logs가 이미 기록(중복), delivery_delayed는 노이즈 → 200 응답 후 무시.

## Scope

- `docs/tickets/T-003_resend-webhook.md` (이 파일)
- `app/config.py` — `resend_webhook_secret` 추가
- `.env.example` — `RESEND_WEBHOOK_SECRET` 추가
- `app/lib/webhook.py` (신설) — svix 서명 검증 (표준 HMAC, 외부 의존성 추가 없음)
- `app/services/engagement.py` (신설) — 이벤트 파싱·send_log 역추적·멱등 적재
- `app/routes/webhooks.py` (신설) — `POST /webhooks/resend`
- `app/main.py` — 라우터 등록
- `tests/routes/test_webhooks.py` (신설)
- Scope 밖: Activity Score 계산, 발송 기능, 봇 필터링 규칙, 와우 포인트(W1~W4) 이벤트

## Acceptance Criteria

- [x] AC1: 유효한 svix 서명의 clicked 이벤트 → `engagement_events`에 1행 적재
      (event_type=clicked, url=클릭 URL, payload=원본, occurred_at=페이로드 시각)
- [x] AC2: 같은 svix-id로 재전송(웹훅 재시도) → 중복 적재 없이 200 (멱등)
      ※ 구현 함정: ORM insert 경로는 rowcount=-1 → RETURNING id로 삽입 여부 판정 (repro로 실증)
- [x] AC3: 서명 불일치/헤더 누락 → 401, 시크릿 미설정 → 503, 본문은 저장 안 됨
- [x] AC4: 타임스탬프가 ±5분 밖(리플레이 공격) → 401
- [x] AC5: `email_id`가 send_logs.provider_id와 일치하면 member_id/newsletter_id/send_log_id 채워짐,
      일치하지 않으면 수신자 이메일로 member 매칭 폴백, 그것도 없으면 고아 이벤트로라도 저장
- [x] AC6: 허용 목록 밖 이벤트(email.sent 등) → 200 응답, 적재 없음
- [x] AC7: `bash scripts/check.sh` 통과 ✅ 44 passed
- [x] AC8 (라이브): Railway 재배포 + Resend 웹훅 등록 후, 테스트 메일 발송 → 민겸·희정이
      열람·클릭 → Supabase `engagement_events`에 실제 행 확인 (2인 테스트)
      ✅ 민겸 실측: delivered/opened/clicked 5행, clicked url=원본 기사 URL 2건.
      ※ 발견: Resend 열람·클릭 추적은 기본 OFF — 추적 서브도메인(links.news) 생성+CNAME 필요했음.
      희정 쪽은 이메일 주소 수령 시 동일 테스트 1통 추가 (파일럿에서 자연 검증돼도 무방).

## Verification

```bash
bash scripts/check.sh
# 라이브 (AC8):
# 1. Resend 대시보드 → Webhooks → Add: https://app-production-945c.up.railway.app/webhooks/resend
#    이벤트: delivered/opened/clicked/bounced/complained 선택 → whsec_ 시크릿 복사
# 2. .env에 RESEND_WEBHOOK_SECRET 추가 → railway-env-sync.sh → railway up
# 3. 테스트 메일 발송(링크 포함) → 열람·클릭 → engagement_events 조회
```

## Notes

- 응답은 즉시(적재 = 단일 INSERT)라 BackgroundTasks 불필요. C4는 /jobs/* 규약이라 비적용,
  단 "잡 본체 로직은 서비스로" 원칙은 동일하게 따름(라우트는 HTTP만).
- 열람(open)은 Apple/Gmail 프록시 오탐으로 보조 신호(결정 5) — 적재는 하되 Score 가중치에서 낮게.
