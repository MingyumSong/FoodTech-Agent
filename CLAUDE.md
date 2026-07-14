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

**프로젝트의 핵심 가치는 "추적 → 점수 → 분류"다.** 이게 아직 미구현이며 최우선이다.
회원 3,000명은 여러 프로그램에 걸쳐 있으므로 `program` 세그먼트로 관리하고, 발송은 전원이 아닌 세그먼트 단위.

---

## 신규 코드베이스 (루트) — 2026-07-12 스캐폴딩 완료

- **스택**: FastAPI + SQLModel + Alembic. uv(Python 3.13). DB: 로컬·테스트 Docker Postgres / 운영 Supabase(`DATABASE_URL`).
- **구조**: `app/{routes,services,models,lib}` — **Route → Service → Model** 계층. 비즈니스 로직은 서비스에, 라우트는 HTTP만.
- **참조 구현**: members 수직 슬라이스 (model→migration→service→route→test). 새 기능은 이 패턴을 따른다.
- **스케줄 작업**: `/jobs/*` 엔드포인트(Bearer `JOBS_TOKEN`, 멱등) ← GitHub Actions 크론이 호출.
- **발송 카나리**: `daily-send-check.yml` 크론이 매일 09:00 KST Resend 검증 메일 1통 발송
  (GitHub Secrets: `RESEND_API_KEY`, `CHECK_EMAIL`). 실패 시 Actions 실패 알림 = 발송 경로 이상 신호.
- **테스트/CI**: pytest + 실제 Postgres(트랜잭션 롤백 픽스처). CI = GitHub Actions(ruff+pyright+pytest).
- **하네스**: `.claude/rules/` 6개 + 스킬(/migrate, /seed-data, /api-test) + 훅(ruff 자동포맷, .env·uv.lock 수정차단).
  아키텍처 결정 기록은 `scaffold-spec.md`.

## 참고 프로토타입 (`archive/foodtech-hub-deploy/` — 수정 금지)

로직 참고·결함 반면교사 용도로만 쓴다. 가져올 로직: 뉴스 수집, CSV 임포트, 매직링크, 캠페인 발송.

- **스택**: FastAPI + SQLModel(ORM). DB는 로컬 SQLite / 운영 PostgreSQL 자동 전환. (신규에서는 SQLite 폐기)
- **프론트**: 정적 단일 HTML (`static/index.html` 공개용, `static/admin.html` 관리자용). Chart.js CDN.
- **이메일**: Resend (`email_client.py`). 키 없으면 DRY RUN 콘솔 출력.
- **뉴스 수집**: `app.py`의 `refresh_news_cache()` — Brave Search API(주력) + Google News RSS(폴백). JSON 캐시, 24h 크론.

### 이미 구현된 것
- 회원 CSV/XLSX 임포트 (`import_members.py`, 한글 헤더 매핑 + 인코딩 자동감지)
- 뉴스레터 캠페인 작성/발송, 수신거부 처리
- 관리자 매직링크 로그인(15분) + 세션(30일)
- 재무 대시보드(yfinance 시가총액/매출, DART 재무제표) — ※ 기획서엔 없던 부가 기능

### ⚠️ 미구현 (여기가 핵심 작업)
- **열람/클릭 추적 없음**. `send_logs.status`에 `opened` 값이 정의만 돼 있고 실제 기록 코드는 없다.
- **회원별·뉴스별 조회 이벤트 테이블 없음**.
- **Activity Score 산출 로직 없음**.
- **Active/Dormant 자동 분류 없음**.

---

## DB 테이블 (프로토타입 db.py — 신규 스키마 설계의 참고)

| 테이블 | 역할 |
|---|---|
| `members` | 회원 명부 (아래 스키마) |
| `newsletters` | 뉴스레터 캠페인 (제목, 본문, 상태, 대상필터, 수신자수) |
| `send_logs` | 발송 로그 (member_id, email, status: queued/sent/failed/**opened**) |
| `magic_links` | 관리자 매직링크 일회용 토큰 |
| `admin_sessions` | 관리자 세션 |

### members 주요 필드
name(필수), email, phone, cohort(기수), category(기업/기관/대학/언론), subcategory,
position, organization, location, division, business_area,
membership_status, membership_type, benefit_pct, council_label,
subscribed(수신동의 기본 true), unsubscribe_token, notes.

---

## 이번 세션에서 확정한 결정

1. **DB: PostgreSQL 단일 원본, 호스팅은 Supabase.** (2026-07-08 변경, 07-11 노션 동기화) 회원 3,000명이라
   Airtable 무료 한도(1,000행) 초과 + 추적 이벤트가 대용량이고, Score는 회원×이벤트 JOIN이라
   같은 DB에 있어야 함. → **Supabase(Postgres) = 회원 + 발송 + 추적 단일 원본**, 관리 UI는 앱의 admin.html,
   **구글시트는 직원 편집용으로 유지하고 주기적으로 임포트**(임포터가 해당 양식 이미 지원).
   Supabase 계정은 희정 생성 → 민겸 팀멤버 초대 → 스키마 설계는 민겸.
   ✅ 보안(2026-07-13): 전 테이블 RLS 활성화(T-002b) + Data API 비활성화 — PostgREST 경로 이중 차단.

2. **크롤링은 API/RSS 소스만.** HTML 스크래핑 제외.
   **뉴스 LLM 분류 체계 = 정부 "푸드테크 10대 핵심분야"** (희정 전달 PDF, 2026-07-12 수령):
   세포배양식품 / 식물기반식품 / 간편식 / 식품프린팅 / 스마트제조 / 스마트유통 /
   커스터마이징 / 외식 푸드테크 / 업사이클링 / 친환경포장.
   - 추가 소스: 네이버 뉴스 API(국내 핵심), 언론사 RSS, 학술은 CrossRef/PubMed API.
   - **안정성 수정 필수**: (a) Brave 한도초과/오류 시에도 RSS로 폴백되게 (현재는 키 부재 시에만 폴백),
     (b) 요청 재시도 + 백오프, (c) 발송 전 뉴스 수집 상태 헬스체크·알림.

3. **추적은 Resend 웹훅이 1차 수단.** (2026-07-11 노션 동기화 — 자체 리다이렉트 단독안 대체)
   - Resend 웹훅(open / click / bounce)을 수신하는 엔드포인트 신설 → 이벤트 테이블에 적재.
     click 페이로드에 클릭된 URL이 포함되므로 뉴스별 집계 가능.
   - 자체 리다이렉트(`/r/{token}`)는 웹훅으로 부족할 때(예: 뉴스 아이템 단위 토큰 매핑)만 보조 검토.
   - 열람(open)은 프록시 오탐 때문에 어차피 보조 신호.
   - 회원별·뉴스별 이벤트 테이블 신설 (member_id, newsletter_id, news_item, event_type, ts).

4. **발송은 4주차에 파일럿으로 조기 시작.** 완벽하지 않아도 시작해서 5·6·7주차 실데이터 누적.
   그 데이터로 Activity Score 가중치를 확정한다.
   파일럿 세그먼트는 **100명 이하**(2026-07-15) — Resend 무료 티어(일 100통) 한도 내, 본 발송 전 Pro($20/월) 전환.

5. **Activity Score = 행동별 가중합.** 열람 < 클릭 < 전달 순으로 가중치.
   열람(open)은 Apple Mail/Gmail 프록시 때문에 신뢰도 낮음 → 보조 신호로만.
   **정밀 지표가 아니라 상대적 순위 도구**로 취급한다.

6. **대시보드는 자체 개발 대신 기존 BI.** Airtable Interfaces로 시작, 필요 시 Metabase.

7. **LLM 호출은 OpenRouter 게이트웨이.** (2026-07-11 노션 동기화) 계정·크레딧은 랩실(희정),
   키 하나로 Claude/GPT/Gemini 호출. OpenAI 호환 엔드포인트(`https://openrouter.ai/api/v1`).
   ✅ 키 수령(`.env`의 OPENROUTER_API_KEY), 잔액 $25, **키 한도 $25 설정 완료**(2026-07-12).
   ✅ **분류 모델 확정(2026-07-14, T-004 드라이런)**: `google/gemini-2.5-flash` 주력
   (실뉴스 80건 4모델 비교 — 일치율 1위·$0.0077/80건·16s, 월 비용 < $1.5 추정).
   haiku-4.5는 스팟체크 보조, gpt-5-mini(지연)·flash-lite("해당없음" 미사용) 제외.
   근거: `docs/research/llm-classification-dryrun.md`.
   **분류 시점 = 수집 시 분류·저장**(2026-07-15) — 발송 직전 실시간 분류 금지, 분류 결과는 뉴스 캐시에 포함.
   ⚠️ 노션 archive 페이지에 OpenRouter 키 평문 노출 발견(2026-07-15) — **로테이션 필요**(미완).

8. **발신 도메인은 발송 전용 서브도메인** — 메인 도메인 평판 보호.
   ✅ **완료(2026-07-12)**: `foodtech-center.org` 신규 구입(Cloudflare, 희정 계정 — 민겸 접근 가능),
   `news.foodtech-center.org`를 Resend에 등록, SPF/DKIM/DMARC 인증 **Verified** (리전 Tokyo).
   관리자 페이지는 추후 `admin.foodtech-center.org`로 연결 예정(앱 배포 후 CNAME).

9. **뉴스 수집 소스 확정(2026-07-13)** — 조사 결과·검증된 피드 URL은 `docs/research/news-sources.md`.
   국내 1차 네이버 뉴스 API(키 발급 희정 대기) + 식품 전문지 RSS 4종 폴백, 해외 Brave 유지
   (⚠️ **무료 티어 폐지** — 월 $5 크레딧, 카드 등록 필요) + 매체 RSS 4종, 학술 OpenAlex + 저널 RSS.
   카카오(뉴스 미지원)·빅카인즈(유료화) 제외. Google News RSS 링크는 인코딩 리다이렉트 URL이라
   클릭 추적 집계 시 디코딩 필요(T-003 설계 때 결정).

10. **뉴스레터 브랜딩 확정(2026-07-13, 희정 컨펌 대기)** — 뉴스레터 **푸디픽**(FOODIE's PICK) ×
    화자 **푸디**, 발신 `푸디 by 푸드테크센터 <foodie@news.foodtech-center.org>`, 매주 목요일.
    코너: 아뮤즈부슈(숫자)→에피타이저(헤드라인3)→메인(심층2)→사이드(논문)→디저트(행사 CTA).
    목업·운용 원칙은 `docs/branding/newsletter-mockup.html`.

11. **와우 포인트 후보 4개 정리(2026-07-13, 간판 선정은 희정 논의 대기)** — 리서치는 `docs/research/wow-features.md`.
    W1 원클릭 투표 / W2 AI 푸디 답장(Resend Inbound, 2025-11 출시 — **간판 제안**) /
    W3 클릭 이력 기반 개인 큐레이션 / W4 매직링크 개인 리캡 페이지. AMP·CSS 인터랙티브는 배제 확정.
    ⚠️ 파생 이슈: 디저트 코너(행사 CTA) 포함 호는 정보통신망법상 "(광고)" 표기 필요 가능 — 법무 확인,
    Outlook Safe Links 봇 클릭은 T-003 추적 정확도 전체에 영향 — 웹훅 설계 때 방어 포함.

12. **배포 PaaS = Railway 선정(2026-07-15).** 월 $5 Hobby, 슬립 없음(웹훅 수신·크론 호출 필수 조건)이 기준.
    계정은 랩실 소유(희정 생성 대기, OpenRouter 패턴). 비용 전망: 파일럿까지 월 $5 → 본 발송 후
    월 ~$25(Resend Pro $20 포함) — 상세는 노션 cost 페이지. 트래킹 노션은 새 워크스페이스 "FoodTech-Agent"로 이전됨.

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

## 추천 다음 작업 (우선순위 순)

- **[보안 P0] OpenRouter 키 로테이션** — 노션 archive에 평문 노출. 신규 키 발급(한도 $25 재설정) + `.env` 교체 + 노션에서 삭제.
- **[보안 P0] GitHub 레포 private 전환** — 회원 PII 임포트 전 필수, 배포 선행.

1. ~~T-001 뉴스 수집 안정화~~ ✅ 2026-07-13 완료 — 네이버(국내 1차)+Brave(해외 1차) → 결과 기반 RSS 폴백,
   백오프 재시도, `POST /jobs/news-refresh` + `GET /health/news`(발송 전 헬스체크). 캐시는 `data/news_cache.json`.
   ⚠️ 후속: 24h 수집 크론 워크플로 추가 필요(발송 티켓과 함께), 학술(OpenAlex) 수집은 별도 티켓.
2. **T-003(예정)** Resend 웹훅 수신 엔드포인트(open/click/bounce) — 공개 URL 필요(앱 배포 선행).
   설계 시 함께 결정: Google News 링크 디코딩, Safe Links 봇 클릭 방어, 와우 포인트(W1~W4) 이벤트 연계.
3. ~~Supabase 프로젝트 연결~~ ✅ 2026-07-12 완료 — T-002 스키마 5테이블 적용됨(리비전 59dda42e7213).
   접속 문자열은 `.env`의 `SUPABASE_URL`(비밀번호 포함 — 커밋 금지, 접두사 `postgresql+psycopg://` 필요).
4. 앱 배포 — **Railway** (희정 계정 대기, 결정 12). 선행: Dockerfile + JOBS_TOKEN 교체 + T-005 티켓.
   배포 후 `admin.foodtech-center.org` CNAME + 24h 수집 크론 연결.
5. Activity Score 산출 함수(가중치는 파라미터로) + Active/Dormant 분류 잡(job).

---

## 명령어 (신규 코드베이스 — 루트에서 실행)

```bash
docker compose up -d postgres          # 로컬 DB 기동
uv run alembic upgrade head            # 스키마 적용
uv run uvicorn app.main:app --reload   # 서버 → http://localhost:8000 (/docs = API 문서)
uv run pytest -q                       # 테스트 (foodtech_test DB 자동 생성)
uv run python scripts/seed.py          # 개발 시드 데이터
bash scripts/check.sh                  # 린트 + 타입체크 + 테스트 일괄 (CI와 동일 단계)
```

프로토타입 구동이 필요하면 `archive/foodtech-hub-deploy/`에서 `pip install -r requirements.txt && python app.py`.
