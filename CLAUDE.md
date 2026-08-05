# FoodTech Hub — 프로젝트 컨텍스트 (Claude Code용)

이 파일은 웹 채팅에서 논의한 내용을 터미널 세션으로 이어가기 위한 핸드오프 문서다.
Claude Code는 세션 시작 시 이 파일을 자동으로 읽는다. 200줄 이내로 유지할 것.

---

## 프로젝트 목표

이기원 교수 운영 푸드테크 집단(최고책임자과정 + 계약학과 + 사업화교육과정 + 월드푸드테크협의회)의
**약 3,000명 회원** 관리 + 주 1회 뉴스레터 자동 발송 + **참여 추적 → Activity Score → 활동/비활동 회원 분류**.
기간 8주(2026-07-06 ~ 08-29). 정례 싱크: 매주 목 **16:30**.

**동기:** 집단이 커지는데 회원 관리가 양식 없이 방치돼 오래된 회원 참여율이 저조. 정기 소통창구를
만들고, **참여율 높은 회원에게 행사·베네핏을 부여**하고 싶음. → "추적 → 점수 → 분류"가 그 선별 근거다.

**프로젝트의 핵심 가치는 "추적 → 점수 → 분류"다.** 추적은 완료(T-003, engagement_events 라이브 적재 중),
**점수(Activity Score)·분류(Active/Dormant)가 남은 최우선**이다.
회원 3,000명은 여러 프로그램에 걸쳐 있으므로 `program` 세그먼트로 관리하고, 발송은 전원이 아닌 세그먼트 단위.

---

## 신규 코드베이스 (루트) — 2026-07-12 스캐폴딩 완료

- **스택**: FastAPI + SQLModel + Alembic. uv(Python 3.13). DB: 로컬·테스트 Docker Postgres / 운영 Supabase(`DATABASE_URL`).
- **구조**: `app/{routes,services,models,lib}` — **Route → Service → Model** 계층. 비즈니스 로직은 서비스에, 라우트는 HTTP만.
- **참조 구현**: members 수직 슬라이스 (model→migration→service→route→test). 새 기능은 이 패턴을 따른다.
- **스케줄 작업**: `/jobs/*`(Bearer `JOBS_TOKEN`, 멱등: news-refresh, newsletter-build,
  newsletter-send, **pilot-daily-send**=매일 13:00 KST 발송). 현황판 `GET /admin/status`(Basic, T-010).
- **발송 카나리**: `daily-send-check.yml` 크론이 매일 09:00 KST Resend 검증 메일 1통 발송
  (GitHub Secrets: `RESEND_API_KEY`, `CHECK_EMAIL`). 실패 시 Actions 실패 알림 = 발송 경로 이상 신호.
- **수집 크론**: `news-refresh.yml` — 매일 07:00 KST 배포 앱의 `/jobs/news-refresh` 호출 후
  `/health/news`로 갱신 검증 (Secrets: `APP_URL`, `JOBS_TOKEN`).
- **테스트/CI**: pytest + 실제 Postgres(트랜잭션 롤백 픽스처). CI = GitHub Actions(ruff+pyright+pytest).
- **하네스**: `.claude/rules/` 6개 + 스킬 6종(migrate·seed-data·api-test·deploy-check·ticket-done·add-env) + 훅(ruff 자동포맷, .env·uv.lock 수정차단).
  아키텍처 결정 기록은 `scaffold-spec.md`.

## 참고 프로토타입 (`archive/foodtech-hub-deploy/` — 수정 금지)

로직 참고 전용(복사 금지, route→service→model로 재작성). 수집·임포트·발송은 재구현 완료라 참고 가치 소멸.
**아직 가져올 로직은 하나뿐**: 관리자 매직링크 로그인 15분 + 세션 30일
(`magic_links`/`admin_sessions`) — 지금 관리자 화면은 Basic 인증 임시다.
신규 스키마의 단일 진실은 Alembic 마이그레이션(Supabase 적용됨, 8테이블): members +
member_programs + newsletters + send_logs + engagement_events + news_items + pilot_members + app_settings.

---

## 이번 세션에서 확정한 결정

1. **DB: PostgreSQL 단일 원본, 호스팅은 Supabase.** (2026-07-08 변경, 07-11 노션 동기화) 회원 3,000명이라
   Airtable 무료 한도(1,000행) 초과 + 추적 이벤트가 대용량이고, Score는 회원×이벤트 JOIN이라
   같은 DB에 있어야 함. → **Supabase(Postgres) = 회원 + 발송 + 추적 단일 원본**, 관리 UI는 앱의
   `GET /admin/status`(T-010, 서버 렌더 HTML — admin.html은 프로토타입 잔재로 폐기),
   **구글시트는 직원 편집용으로 유지하고 주기적으로 임포트**(임포터가 해당 양식 이미 지원).
   ✅ 보안: 전 테이블 RLS 활성화(T-002b) + Data API 비활성화 — PostgREST 경로 이중 차단.

2. **크롤링은 API/RSS 소스만.** HTML 스크래핑 제외.
   **뉴스 LLM 분류 체계 = 정부 "푸드테크 10대 핵심분야"**: 세포배양식품 / 식물기반식품 / 간편식 /
   식품프린팅 / 스마트제조 / 스마트유통 / 커스터마이징 / 외식 푸드테크 / 업사이클링 / 친환경포장.
   ✅ 안정성(결과 기반 폴백·재시도·헬스체크)은 T-001로 구현 완료. 소스 목록은 결정 9.

3. **추적은 Resend 웹훅이 1차 수단.** (2026-07-11) ✅ T-003 구현 완료 — `POST /webhooks/resend`(svix
   서명 검증) → `engagement_events` 멱등 적재, clicked url=원본 기사 URL(캐시 매칭). 상세는 티켓.
   열람(open)은 프록시 오탐 때문에 보조 신호. 추적 도메인 `links.news.foodtech-center.org` Verified.

4. **발송은 4주차에 파일럿으로 조기 시작** — 실데이터로 Activity Score 가중치를 확정한다.
   파일럿 세그먼트는 **100명 이하** — Resend 무료 티어(일 100통) 한도, 본 발송 전 Pro($20/월) 전환.
   ✅ 파일럿 = 랩실 25명, 매일 13:00 발송 중 — 9회분 실데이터가 T-017 가중치의 근거가 됐다.

5. **Activity Score = 발송 대비 참여 비율** (✅ T-017 확정·배포). 열람 < 클릭 < 반응
   ('전달'은 관측 불가라 원클릭 반응이 그 자리를 대신함). **편당 최고 행동 하나만** 값으로 매긴다
   (열람1 / 클릭3 + URL 추가당 0.5 최대 +2 / 반응5) — 같은 편 재열람 22회가 점수를 못 올린다.
   반감기 30일·창 120일·축소 K=3, 발송 후 10초 내 열람은 봇으로 제외. **합계가 아니라 비율이라
   활동량으로 읽으면 안 된다** — 정밀 지표가 아닌 상대적 순위 도구. 등급은 절대 컷
   `active≥30 / warm≥10 / dormant` + `unknown`(창 안 발송 0 — dormant와 구분) / `unsubscribed`,
   백분위는 저장 없이 조회 시점 계산. **튜닝 상수는 `app/services/activity_score.py` 상단 한 곳.**

6. ~~기존 BI(Airtable/Metabase)~~ → **폐기**: 관리 화면은 앱이 서버 렌더로 직접 제공
   (`/admin/*` 5탭 — 현황·회원관리·인기분야·참여도·발송검토).

7. **LLM 호출은 OpenRouter 게이트웨이.** (2026-07-11 노션 동기화) 계정·크레딧은 랩실(희정),
   키 하나로 Claude/GPT/Gemini 호출. OpenAI 호환 엔드포인트(`https://openrouter.ai/api/v1`).
   ✅ 키 수령(`.env`의 OPENROUTER_API_KEY), 잔액 $25, **키 한도 $25 설정 완료**(2026-07-12).
   ✅ **분류 모델 = `google/gemini-2.5-flash`**(T-004 드라이런 — 실뉴스 80건 4모델 비교에서 일치율
   1위·$0.0077/80건, 월 < $1.5). 탈락 사유는 `docs/research/llm-classification-dryrun.md`.
   **분류 시점 = 수집 시 분류·저장** — 발송 직전 실시간 분류 금지.
   노션 archive에 키 평문 있음 — 2인 전용 워크스페이스라 **로테이션 불필요 판단**(민겸).

8. **발신 도메인은 발송 전용 서브도메인** — 메인 도메인 평판 보호.
   ✅ **완료(2026-07-12)**: `foodtech-center.org` 신규 구입(Cloudflare, 희정 계정 — 민겸 접근 가능),
   `news.foodtech-center.org`를 Resend에 등록, SPF/DKIM/DMARC 인증 **Verified** (리전 Tokyo).
   관리자 페이지는 `admin.foodtech-center.org` 연결 완료(2026-08-06, DNS-only CNAME).

9. **뉴스 수집 소스 확정(2026-07-13)** — 조사 결과·검증된 피드 URL은 `docs/research/news-sources.md`.
   국내 1차 네이버 뉴스 API + 식품 전문지 RSS 4종 폴백, 해외 Brave(⚠️ **무료 티어 폐지** — 월 $5
   크레딧, 카드 등록 필요) + 매체 RSS 4종, 학술 OpenAlex + 저널 RSS.
   카카오(뉴스 미지원)·빅카인즈(유료화) 제외. Google News RSS 링크는 인코딩 리다이렉트 URL이라
   클릭 추적 집계 시 디코딩 필요(T-003 설계 때 결정).

10. **뉴스레터 브랜딩 확정(2026-07-13, 희정 컨펌 대기)** — 뉴스레터 **푸디픽**(FOODIE's PICK) ×
    화자 **푸디**, 발신 `푸디 by 푸드테크센터 <foodie@news.foodtech-center.org>`, 매주 목요일.
    **코너(T-013 v2)**: 오늘의 분야 줄 → 에피타이저 2 → 메인 3 → 디저트(원클릭 반응 3버튼).
    현재 시안은 `docs/branding/newsletter-v2.html`(mockup.html은 v1 기록용).

11. **와우 포인트 후보(2026-07-13, 간판 선정 대기)** — `docs/research/wow-features.md`.
    ✅W1 원클릭 반응(T-013) / W2 AI 푸디 답장(**간판 제안**) / W3 개인 큐레이션 / W4 개인 리캡.
    ⚠️ 행사 CTA를 넣는 호는 정보통신망법상 "(광고)" 표기 필요 가능 — 법무 확인 대상.

12. **배포 PaaS = Railway**(월 $5 Hobby, 슬립 없음 — 웹훅 수신·크론 호출의 필수 조건).
    비용 전망: 파일럿 월 $5 → 본 발송 후 월 ~$25(Resend Pro 포함) — 상세는 노션 cost 페이지.
    **주차 진행 현황(Done/To do)은 노션 `Project ▸ is on track`의 주차 페이지에 기록**
    (레포 docs 아님 — docs는 티켓·research용). 시크릿은 노션에 평문 저장·복제 금지.

---

## 개발 워크플로 — 티켓 기반 (docs/tickets/)

구현 작업은 `docs/tickets/`의 마크다운 티켓을 요구사항의 단일 진실로 삼는다.

- **티켓이 필요한 문턱**: 여러 세션에 걸치는 작업, DB 스키마 변경, 3파일 이상 수정.
  그보다 작은 수정(오타, 단일 함수 버그픽스)은 티켓 없이 바로 진행해도 된다.
- 티켓 양식은 `docs/tickets/_TEMPLATE.md` (Problem / Context / Scope / AC / Verification).
- 티켓의 **Scope 밖 파일은 수정하지 않는다**. 코딩 전에 수정 파일 목록(계획)을 먼저 출력한다.
- 완료 기준: Acceptance Criteria 충족 + Verification 절차 통과 → Status를 DONE으로 갱신 후 커밋.
- 대화에서 계획이 확정되면 그 자리에서 티켓 파일로 저장한다 (티켓 = 합의된 계획의 저장본,
  다음 세션으로의 핸드오프 문서).

## 완료된 기반 (상세는 각 티켓 — 여기선 계속 쓰이는 사실만)

T-001·T-006 수집·분류 / T-002 스키마 / T-003 웹훅 / T-005 배포 / T-007 임포터 / T-008 발송 /
T-010 현황판 / T-011 매일발송 / T-012 관리자 — **전부 DONE·배포·라이브 검증 완료.**

계속 유효한 사실만 추림:

- **배포**: `https://app-production-945c.up.railway.app`, 프로젝트 foodtech-hub / 서비스 app
  (교수님 계정 snupfm@gmail.com). `railway up`으로 배포, 환경변수는 `scripts/railway-env-sync.sh`.
- **DB**: `.env`의 `SUPABASE_URL`(비밀번호 포함 — 커밋 금지, 접두사 `postgresql+psycopg://`).
  운영 마이그레이션은 `DATABASE_URL="$SUPABASE_URL" uv run alembic upgrade head`.
  **코드보다 먼저 적용할 것** — 새 테이블을 읽는 코드가 먼저 뜨면 조회가 터진다.
- **회원**: Supabase 3,413명(이메일 94%). 파일럿 `pilot-daily` 25명 = `pilot-lab-1`~`5` 각 5명.
  A/B에 쓰되 **사전 참여도가 그룹마다 2배 이상 다르다**(평균 1조 24.6 / 4조 23.2 / 5조 17.4 /
  3조 11.1 / 2조 10.6) → T-016 실험은 대조군을 그냥 고르지 말고 **짝을 맞출 것**.
- **수집**: 네이버 `display` 100, 비대칭 캡(`MAX_DOMESTIC=120`/`MAX_OVERSEAS=40`), 분야 균형
  라운드로빈(`_cap_balanced`). 분류 프롬프트 v3(정부 공식 정의 삽입). **입력은 제목+요약 300자**
  (본문 스크래핑 안 함). 2차 게이트(`filter_foodtech_relevant`)는 발송 직전 LLM.
- **추적**: 추적 도메인 `links.news.foodtech-center.org`(Resend 추적 기본 OFF라 필수였음).
  clicked url = 원본 기사 URL — 이게 T-016에서 깨질 전제다.
- **`pilot_members`**(RLS): 25명 스냅샷+집계. 점수 컬럼은 `refresh_pilot_stats`(**파일럿 경로 전용** —
  본 발송은 안 탄다)가 남기는 **이력 스냅샷일 뿐**. 참여도 탭은 **조회 시점에 재계산**한다.

## 2026-08-06 세션 (T-009·T-023 — 둘 다 배포·라이브 검증)

- ✅ **T-009 기사 큐레이션**(`curation.py`) — 같은 사건 중복이 풀의 13.9%였다. 제목 토큰 자카드
  **0.30**(오검출 시작점 0.28을 실측해 정함). **연쇄 금지** — 묶음기사가 다리가 돼 서로 다른 두 사건이
  뭉쳤다. 대표와 **직접** 닮은 것만(`cluster_of`). 묶음기사는 풀에서 제외(`is_roundup`).
  대표는 `source_tier` 0/1/2 — 표시용 `SOURCE_BY_DOMAIN`과 분리한 `PREFERRED_SOURCE_DOMAINS`다.
  신뢰도는 **필터가 아니다**(매핑률 29%·해외 1/15 → 필터면 굶는다). `NON_NEWS_DOMAINS` 2→40여 개.
  **T-018 매체명 3건이 한 칸씩 밀려 있었다** — foodnews=식품저널/thinkfood=식품음료신문/
  foodbank=식품외식경제로 교정. 운영 158 → 123 (제거 35건 22.2%).
- ⚠️ **T-023 Score 활용 (PARTIAL)** — `/admin/scores.csv?tier=`(Basic, BOM) + 참여도 탭 버튼은 완료.
  **등급 발송은 메커니즘(`target_filter.tiers`)만 있고 진입점이 없다** — `tiers`를 넘기는 프로덕션
  코드가 0줄(테스트뿐). 급하지 않아 미룬 것, 티켓 "남은 일" 참조.
  **대상은 조립 시점에 확정해 `member_ids`로 얼린다** — 발송이 `send_logs`에 무반응 1건을 더해
  점수를 낮춰 재시도에서 대상이 1→0명이 됐다. 수신거부만 안 얼리고 발송 시점 목록과 교집합.
- **관리자 도메인 라이브**: `https://admin.foodtech-center.org`. 단 `PUBLIC_BASE_URL`은 **그대로 Railway URL** — 수신거부·반응 링크의 기준이라 바꾸면 기존 메일과 갈린다.

## 2026-08-04 세션 (파일럿 수신자 피드백 6건 반영 — T-013~T-018, 전부 배포됨)

- ✅ **T-013 뉴스레터 v2** — **에피2 + 메인3 + 디저트**, **국내4:해외1**(해외는 메인에),
  맨 위 "오늘의 분야" 줄. 디저트 = **원클릭 반응 3버튼**: `engagement_events`(`reacted` + payload)라
  스키마 변경 없고 (회원,편) 멱등, 토큰은 `member.unsubscribe_token` 재사용. 폭은 `max-width`.
  헤더 아이콘 `app/static/foodie-icon.png`(네이비 `#042A4F`는 에셋 샘플값 — 변경 금지).
  **답장 버그도 함께 수정**: 발신 도메인에 MX가 없고 `reply_to`도 없어 푸터의 "답장하면 읽습니다"가
  거짓이었다 → `newsletter_reply_to`(= 교수님 지메일). **잔여: 실제 메일에서 답장 도달 확인.**
- ✅ **T-014 관리자 발송 설정** — `app_settings`(key/value JSONB, RLS) + 발송검토 탭 폼.
  **행이 없으면 코드 기본값.** 수신자 상한 100은 일부러 설정에서 제외(결정 4 안전장치).
- ✅ **T-015 체류 근사** — 원문 체류는 측정 불가(남의 서버). **같은 편 안의 연속 클릭 간격**으로 근사
  (`dwell.py`, 30분 상한, 편별 마지막 클릭 제외). 인기분야 탭에 "읽은 깊이" 카드.
  실측: 측정가능 47%, 중앙값 13초, **튕김 24 : 중간 23 : 정독 16** — 절반이 제목만 보고 닫는다.
- ✅ **T-017 Activity Score + T-019 참여도 탭** — **봇 열람(발송 후 10초) 필터가 실제로 물었다**:
  9편 전부 즉시 열람이던 1명이 warm→dormant로 뒤집혔다(원시 집계로는 '전편 열람' 우수 회원).
- ✅ **T-018 매체명** — `news_items` 460건 전부 `source`가 비어 있었다(회귀가 아니라 처음부터).
  URL 호스트에서 복원 + **도메인 폴백** — 모르면 지어내지 않는다. 460건 백필 완료.
- **T-016 착지 페이지 = 유일한 미착수.** 시안·A/B 설계 확정, 선결 질문 4개 중 3개 해결(티켓 참조).
  **미해결 = 이탈 비용** — 2주 A/B로 답이 나온다. 단 조 단위 배정은 금물(위 참여도 격차) — **점수
  순위로 5블록×5명 층화 배정 + 회원별 사전/사후 변화로 판정**, 기준선은 실험 시작 전 동결.
  까다로운 곳: 기사 링크를 수신자별로 바꿔야 하고(T-013의 "원본 URL 변형 금지"를 의도적으로 깸),
  그러면 T-003 매칭이 `engagement.py`·`pilot_daily.py`·`admin_pages.py` 3곳에서 2경로를 지원해야 한다.

**알아둘 것**: `/health/news`는 디스크 JSON 캐시를 봐서 **배포마다 빨간불**(07:00 크론이 복구, 발송은
DB를 읽으므로 무관). **도구**: `scripts/dbq.sh {prod|local} "SQL"`(읽기 전용 강제)·`scripts/shot.sh`.

## 명령어 (신규 코드베이스 — 루트에서 실행)

```bash
docker compose up -d postgres          # 로컬 DB 기동
uv run alembic upgrade head            # 스키마 적용
uv run uvicorn app.main:app --reload   # 서버 → http://localhost:8000 (/docs = API 문서)
bash scripts/check.sh                  # 린트 + 타입체크 + 테스트 일괄 (CI와 동일 — 이것만 돌리면 된다)
```
