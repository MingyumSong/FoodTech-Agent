# C4: /jobs/* 엔드포인트 규약

스케줄 작업(뉴스 수집, 발송, Score 계산)은 GitHub Actions 크론이 호출하는 `/jobs/*` 엔드포인트로 만든다.

- 인증: `Authorization: Bearer $JOBS_TOKEN` — `app/routes/jobs.py`의 `require_jobs_token` 의존성 재사용.
- 멱등: 같은 요청이 두 번 와도 안전해야 한다 (중복 발송/중복 적재 방지 로직 필수).
- 즉시 응답: 장시간 작업은 BackgroundTasks 등으로 넘기고 바로 응답한다. 크론 호출이 타임아웃되면 안 된다.
- 잡 본체 로직은 라우트에 두지 말고 서비스 함수로 분리 — 트리거(크론)를 나중에 교체할 수 있게.
