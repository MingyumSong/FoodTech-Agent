# T-008: 발송 최소형 — 푸디픽 조립 + Resend 발송 + send_logs (파일럿)

Status: TODO (2026-07-19 초안 — 세션 랩에서 작성, 다음 세션 착수 합의됨)

## Problem

발송 기능이 코드 0줄이다. 원래 그림 6단계 중 마지막 큰 조각(④)이며, 이게 완성돼야
4주차 파일럿 발송 → 5~7주차 실데이터 누적 → Activity Score 가중치 확정(결정 4)이 굴러간다.

## Context (검증된 사실)

- `Newsletter` 모델 완비(target_filter JSONB, status, sent/failed counts) — **스키마 신설 불필요 예상**.
- `send_logs.provider_id`(unique) 존재 — "Resend email_id로 웹훅 역추적하는 조인 키" (T-002).
- 회원 3,413명 Supabase 임포트 완료(T-007), 전원 `unsubscribe_token` 보유. **수신거부 엔드포인트는 없음**.
- 추적 인프라 가동 중(T-003): 웹훅 수신 + 추적 도메인 links.news Verified. Resend 추적은 발송 시 활성 확인.
- 프로토타입 `email_client.py` 참고(재작성, C5): 키 없으면 DRY RUN 패턴.
- 브랜딩(결정 10): 푸디픽 코너 구조, 발신 `푸디 by 푸드테크센터 <foodie@news.foodtech-center.org>`,
  목업 `docs/branding/newsletter-mockup.html`. ⚠️ 희정 컨펌 대기.

## Scope 필수 요소 (세션 랩 분석, 2026-07-19)

1. Resend 발송 클라이언트 (`app/lib/` 또는 서비스) — 키 부재 시 DRY RUN, rate limit(2 req/s) 대응.
2. **`send_logs.provider_id` = Resend 응답 email_id 저장** — 누락 시 T-003 웹훅이 전부 이메일
   폴백/고아 매칭으로 떨어짐. 수신자당 1행, queued→sent/failed.
3. 파일럿 세그먼트 가드 — target_filter(program)+`subscribed=True`, **수신자 100 초과 시 발송 거부**
   (결정 4, Resend 무료 일 100통).
4. 푸디픽 템플릿 조립 — 뉴스 소스는 `news_items`(⚠️ T-006 배포 HOLD 해제 선행).
   **링크 URL은 DB 저장 원본 그대로** — 클릭 URL 문자열 매칭(T-003 설계 결정 1)의 전제. 단축·변형 금지.
5. 수신거부 — `GET /unsubscribe/{token}` → subscribed=False + 푸터 링크 +
   `List-Unsubscribe`/RFC 8058 one-click 헤더(Gmail 대량 발송 요건).
6. C4 규약 — `POST /jobs/send-newsletter`(Bearer, BackgroundTasks 즉시 응답),
   **멱등**: 재호출 시 send_logs에 이미 sent인 수신자 재발송 금지.
7. newsletters 상태 전이 draft→sending→sent + total/sent/failed 카운트.
8. 열림 문제(구현 전 결정): 사이드(논문) 코너 — OpenAlex 미구현이라 파일럿에선 생략/수동 택일.
   디저트(행사 CTA) — "(광고)" 표기 법무 이슈(결정 11)로 파일럿 포함 여부 결정.

## 선행 조건

- [ ] T-006 배포 HOLD 해제 (희정 분류 컨펌 → 프롬프트 보정 → railway up) — 뉴스 재료의 전제
- [ ] 파일럿 세그먼트·발송 시점 확정 (7/23 싱크, 교수님 확인)
- [ ] 푸디픽 브랜딩 컨펌 (희정)

## Acceptance Criteria (초안 — 착수 시 구체화)

- [ ] AC1: DRY RUN 모드로 푸디픽 HTML 조립 결과 확인 가능 (키 없이 로컬 검증)
- [ ] AC2: 발송 시 수신자별 send_logs 생성 + provider_id 저장 → 웹훅 이벤트가 member_id로 자동 연결
- [ ] AC3: 같은 뉴스레터 재발송 호출 → 이미 sent인 수신자 스킵 (멱등)
- [ ] AC4: 100명 초과 세그먼트 → 발송 거부
- [ ] AC5: 수신거부 링크 클릭 → subscribed=False, 이후 발송 대상 제외
- [ ] AC6: check.sh 통과 + 민겸·희정 대상 실발송 1회 → open/click이 member_id와 함께 적재

## Verification

착수 시 작성. 핵심: DRY RUN 조립 → 2인 실발송 → Supabase에서 send_logs·engagement_events 조인 확인.
