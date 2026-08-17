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
- **크론**: `daily-send-check.yml`(09:00 KST Resend 카나리 1통 — 실패 = 발송 경로 이상 신호) /
  `news-refresh.yml`(07:00 KST `/jobs/news-refresh` 후 `/health/news` 검증) / `pilot-daily-send.yml`.
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

2. **크롤링은 API/RSS 소스만.** HTML 스크래핑 제외. 소스 목록은 결정 9.
   **뉴스 LLM 분류 체계 = 정부 "푸드테크 10대 핵심분야"**: 세포배양식품 / 식물기반식품 / 간편식 /
   식품프린팅 / 스마트제조 / 스마트유통 / 커스터마이징 / 외식 푸드테크 / 업사이클링 / 친환경포장.

3. **추적은 Resend 웹훅이 1차 수단.** ✅ T-003 — `POST /webhooks/resend`(svix 서명 검증) →
   `engagement_events` 멱등 적재, clicked url=원본 기사 URL. 열람(open)은 프록시 오탐 때문에 보조 신호.

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

7. **LLM 호출은 OpenRouter 게이트웨이.** 계정·크레딧은 랩실(희정), 키 한도 $25 설정 완료.
   ✅ **분류 모델 = `google/gemini-2.5-flash`**(T-004 드라이런 — 실뉴스 80건 4모델 비교 일치율
   1위·$0.0077/80건). 탈락 사유는 `docs/research/llm-classification-dryrun.md`.
   **분류 시점 = 수집 시 분류·저장** — 발송 직전 실시간 분류 금지.

8. **발신 도메인은 발송 전용 서브도메인** — 메인 도메인 평판 보호. ✅ `foodtech-center.org`
   (Cloudflare, 희정 계정), `news.` 를 Resend 등록 SPF/DKIM/DMARC **Verified**(Tokyo),
   `admin.` 은 관리자 페이지(DNS-only CNAME).

9. **뉴스 수집 소스 확정** — 검증된 피드 URL은 `docs/research/news-sources.md`. 국내 네이버 API +
   식품 전문지 RSS 4종 폴백, 해외 Brave(⚠️ **무료 티어 폐지** — 월 $5) + 매체 RSS 4종, OpenAlex.
   Google News RSS는 인코딩 리다이렉트 URL이라 클릭 집계 시 디코딩 필요.

10. **브랜딩** — **푸디픽**(FOODIE's PICK) × 화자 **푸디**, 발신 `푸디 by 푸드테크센터
    <foodie@news.foodtech-center.org>`. **코너**: 오늘의 분야 → 에피2 → 메인3 → 디저트(반응 3버튼).
    시안 `docs/branding/newsletter-v2.html` — **시안이라 여길 고쳐도 메일은 안 바뀐다**(ui-map 참조).

11. **와우 포인트 후보(간판 선정 대기)** — `docs/research/wow-features.md`. ✅W1 원클릭 반응 /
    W2 AI 푸디 답장(**간판 제안**) / W3 개인 큐레이션 / W4 개인 리캡.
    ⚠️ 행사 CTA를 넣는 호는 정보통신망법상 "(광고)" 표기 필요 가능 — 법무 확인 대상.

12. **배포 PaaS = Railway**(월 $5 Hobby, 슬립 없음 — 웹훅 수신·크론 호출의 필수 조건). 비용은
    파일럿 월 $5 → 본 발송 후 ~$25(Resend Pro 포함), 상세는 노션 cost 페이지. **주차 진행
    현황(Done/To do)은 노션 `Project ▸ is on track`의 주차 페이지에** (레포 docs는 티켓·research용).

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

- **배포**: `https://app-production-945c.up.railway.app`, 프로젝트 foodtech-hub / 서비스 app
  (교수님 계정 snupfm@gmail.com). `railway up`으로 배포, 환경변수는 `scripts/railway-env-sync.sh`.
- **DB**: `.env`의 `SUPABASE_URL`(비밀번호 포함 — 커밋 금지, 접두사 `postgresql+psycopg://`).
  운영 마이그레이션은 `DATABASE_URL="$SUPABASE_URL" uv run alembic upgrade head`.
  **코드보다 먼저 적용할 것** — 새 테이블을 읽는 코드가 먼저 뜨면 조회가 터진다.
- **회원**: Supabase 3,413명(이메일 94%). 파일럿 `pilot-daily` 25명 = `pilot-lab-1`~`5` 각 5명.
  **사전 참여도가 그룹마다 2배 이상 다르다**(1조 24.6 / 4조 23.2 / 5조 17.4 / 3조 11.1 / 2조 10.6)
  → 실험은 조 단위 배정 금물, **짝을 맞출 것**.
- **수집**: 네이버 `display` 100, 비대칭 캡(`MAX_DOMESTIC=120`/`MAX_OVERSEAS=40`), 분야 균형
  라운드로빈(`_cap_balanced`). 분류 프롬프트 v3(정부 공식 정의 삽입). **입력은 제목+요약 300자**
  (본문 스크래핑 안 함). 2차 게이트(`filter_foodtech_relevant`)는 발송 직전 LLM, **temperature=0**.
- **추적**: 추적 도메인 `links.news.foodtech-center.org`(Resend 추적 기본 OFF라 필수였음).
  clicked url = 원본 기사 URL — 이게 T-016에서 깨질 전제다.
- **UI 어디를 고치나**: `docs/guide/ui-map.md` (템플릿 파일이 아니라 파이썬 함수가 HTML을 조립).
- **`pilot_members`**(RLS): 25명 스냅샷+집계. 점수 컬럼은 `refresh_pilot_stats`(**파일럿 경로 전용** —
  본 발송은 안 탄다)가 남기는 **이력 스냅샷일 뿐**. 참여도 탭은 **조회 시점에 재계산**한다.

## 계속 유효한 사실 — T-009·T-023·T-024·T-025 (상세는 각 티켓)

- **큐레이션**(`curation.py`): 제목 토큰 자카드 **0.30**, **연쇄 금지**(대표와 직접 닮은 것만).
  ⚠️ **테스트 픽스처 제목이 서로 닮으면 전부 병합돼 풀이 마른다** — 이 함정에 세 번 걸렸다.
  픽스처 제목은 공통 어절이 없게 지을 것.
- ⚠️ **T-023 (PARTIAL)** — 등급 발송은 메커니즘만 있고 진입점이 없다(`tiers`를 넘기는 코드 0줄).
  **대상은 조립 시점에 `member_ids`로 얼린다** — 발송이 자기 수신자 자격을 박탈해 1→0명이 됐다.
- **관리자 도메인**: `https://admin.foodtech-center.org`. 단 `PUBLIC_BASE_URL`은 **그대로
  Railway URL** — 수신거부·반응 링크의 기준이라 바꾸면 기존 메일과 갈린다.

## 2026-08-17 세션 (T-027 대시보드 통합 — 5단계 전부 배포·라이브 검증)

**희정님 대시보드 프론트를 우리 레포로 가져와** FastAPI가 서빙한다(`/admin/dashboard`).
네 섹션 중 **04 Newsletter만 우리가 채우고** 나머지 셋은 랩실이 이어받을 빈 자리로 남겼다.
계획·구조 그림은 T-027 티켓 맨 위 링크.

- **렌더링이 바뀌었다**: 파이썬 f-string HTML 조립 → **JSON API + 클라이언트 렌더**.
  기준은 "우리가 편한 것"이 아니라 **"이어받는 사람이 읽기 쉬운 것"**.
  확장 지점은 `dashboard.js`의 `SECTIONS` 한 곳 — endpoint·render·actions만 채우면 섹션이 된다.
- **기존 5탭(`/admin/status` 등)은 그대로 살아 있다.** `/admin`도 아직 현황판으로 간다.
- **셸 HTML은 `app/templates/`** — `app/static/`은 공개 마운트라 거기 두면 인증이 통째로 우회된다.
- **집계 범위를 값과 함께 보낸다** — 구독자는 전체 3,421명, 참여율은 파일럿 25명 기준.
- **발송 가능 여부는 서버가 판정**(`can_send`)하고 누르는 시점에 재판정한다.
- ✅ **발송 대상 토글 신설** — 이미 있는 회원을 명단에 넣는 기능이 없어서 8/17 교수님 요청 때
  스크립트를 돌려야 했다. 프로그램(명단)과 구독(수신 의사)은 **분리해서** 다룬다.
- ✅ **개발 모드**(`Settings.dev_mode`) — `ADMIN_TOKEN` 없음 **AND** `APP_ENV∈{local,dev,test}`
  일 때만 인증이 꺼진다. 운영은 `APP_ENV=prod`라 안 열린다. 화면 배너+기동 로그로 알린다.
  `bash scripts/dev.sh` 한 줄이면 클론 직후 화면까지. **동작 변경**: 예전엔 토큰 없으면
  무조건 503이었다.
- ⚠️ **`ADMIN_TOKEN` 로테이션 필요** — 대시보드 Cloudflare에 통째로 들어가 있고(발송 실행까지
  여는 열쇠), 8/17 작업 중 터미널 출력에도 노출됐다.

## 2026-08-17 세션 2 (T-028 게이트 붕괴 — 배포·재현 검증)

- ⚠️ **LLM 판정은 배치 크기가 정한다.** 게이트가 풀 전체(117건)를 한 번에 던져 **drop 0**,
  심도가 평평해지며 T-024의 "심도로 메인 선정"이 무효가 됐다(아파트 분양 기사가 #026 제목).
  **`BATCH_SIZE`(20)로 쪼개면 drop 31** — 프롬프트가 아니라 **한 호출에 몇 건인가**를 먼저 본다.
- **크론 초록불 = 발송 결과**(`GET /jobs/pilot-daily-status`). 예전엔 트리거 202만 봐서
  그날 발송이 통째로 빠져도 초록불이었다(8/14 수집 실패가 그렇게 지나갔다).
- 경로·쿼리 없는 **루트 URL은 기사가 아니다** — `thedieline.com/`이 해외 꼭지로 실렸다.

## 2026-08-09 세션 (파일럿 피드백 5건 — T-024·T-025, 전부 배포)

- ✅ **T-024 심도 편성** — 근본 원인은 `_call_openrouter`가 **temperature를 안 넘긴 것**이었다
  (같은 풀 112건 → drop 31 vs 13). `temperature=0` 고정 후 재현된다. 심도는 이진이 변별을 못 해
  **1~5 등급**. 칼럼·기획연재·인물인터뷰·지자체 예산 활동은 drop.
- ⚠️ **그 정렬이 '기사 회전'을 깼다** — 예전엔 분야별 **최신** 1건이라 자연히 교체됐는데 심도 4는
  7일 창 내내 앞자리를 지킨다. → `_drop_already_sent`(지난 편 URL을 `target_filter.item_urls`에).
  **풀이 얇으면 배제를 포기**한다 — 중복 노출보다 발송 실패가 나쁘다.
- ✅ **T-025 수신거부** — GET이 누르는 즉시 해지시켰다(프리페치·오클릭 동일). GET은 확인 페이지만,
  해지는 POST에서만. **되돌릴 경로가 없어서** 회원관리에 토글 신설(본인 요청 전제).

**알아둘 것**: `/health/news`는 디스크 JSON 캐시를 봐서 **배포마다 빨간불**(07:00 크론이 복구, 발송은
DB를 읽으므로 무관). **도구**: `scripts/dbq.sh {prod|local} "SQL"`(읽기 전용 강제)·`scripts/shot.sh`.

## 명령어 (신규 코드베이스 — 루트에서 실행)

```bash
docker compose up -d postgres          # 로컬 DB 기동
uv run alembic upgrade head            # 스키마 적용
uv run uvicorn app.main:app --reload   # 서버 → http://localhost:8000 (/docs = API 문서)
bash scripts/check.sh                  # 린트 + 타입체크 + 테스트 일괄 (CI와 동일 — 이것만 돌리면 된다)
```
