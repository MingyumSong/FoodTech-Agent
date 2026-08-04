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
- **스케줄 작업**: `/jobs/*` 엔드포인트(Bearer `JOBS_TOKEN`, 멱등: news-refresh,
  newsletter-build, newsletter-send) ← 크론/수동 호출. 현황판은 `GET /admin/status`(Basic, T-010).
- **발송 카나리**: `daily-send-check.yml` 크론이 매일 09:00 KST Resend 검증 메일 1통 발송
  (GitHub Secrets: `RESEND_API_KEY`, `CHECK_EMAIL`). 실패 시 Actions 실패 알림 = 발송 경로 이상 신호.
- **수집 크론**: `news-refresh.yml` — 매일 07:00 KST 배포 앱의 `/jobs/news-refresh` 호출 후
  `/health/news`로 갱신 검증 (Secrets: `APP_URL`, `JOBS_TOKEN`).
- **테스트/CI**: pytest + 실제 Postgres(트랜잭션 롤백 픽스처). CI = GitHub Actions(ruff+pyright+pytest).
- **하네스**: `.claude/rules/` 6개 + 스킬(/migrate, /seed-data, /api-test) + 훅(ruff 자동포맷, .env·uv.lock 수정차단).
  아키텍처 결정 기록은 `scaffold-spec.md`.

## 참고 프로토타입 (`archive/foodtech-hub-deploy/` — 수정 금지)

로직 참고 전용(복사 금지, route→service→model로 재작성). 뉴스 수집·CSV 임포트는 T-001/T-006/T-007로
재구현 완료라 참고 가치 소멸. **아직 가져올 로직**: ① 캠페인 발송·수신거부 (`email_client.py` —
키 없으면 DRY RUN, `send_logs`/`newsletters` 흐름) — 발송 티켓(T-008)에서,
② 관리자 매직링크 로그인 15분 + 세션 30일 (`magic_links`/`admin_sessions`) — 관리자 페이지에
쓰기 기능(발송 버튼 등) 붙일 때. 읽기 전용 현황판은 T-010으로 이미 배포됨(Basic 인증 임시).
신규 스키마의 단일 진실은 Alembic 마이그레이션(Supabase 적용됨): members + member_programs +
newsletters + send_logs + engagement_events + news_items.

---

## 이번 세션에서 확정한 결정

1. **DB: PostgreSQL 단일 원본, 호스팅은 Supabase.** (2026-07-08 변경, 07-11 노션 동기화) 회원 3,000명이라
   Airtable 무료 한도(1,000행) 초과 + 추적 이벤트가 대용량이고, Score는 회원×이벤트 JOIN이라
   같은 DB에 있어야 함. → **Supabase(Postgres) = 회원 + 발송 + 추적 단일 원본**, 관리 UI는 앱의
   `GET /admin/status`(T-010, 서버 렌더 HTML — admin.html은 프로토타입 잔재로 폐기),
   **구글시트는 직원 편집용으로 유지하고 주기적으로 임포트**(임포터가 해당 양식 이미 지원).
   Supabase 계정은 희정 생성 → 민겸 팀멤버 초대 → 스키마 설계는 민겸.
   ✅ 보안(2026-07-13): 전 테이블 RLS 활성화(T-002b) + Data API 비활성화 — PostgREST 경로 이중 차단.

2. **크롤링은 API/RSS 소스만.** HTML 스크래핑 제외.
   **뉴스 LLM 분류 체계 = 정부 "푸드테크 10대 핵심분야"** (희정 전달 PDF, 2026-07-12 수령):
   세포배양식품 / 식물기반식품 / 간편식 / 식품프린팅 / 스마트제조 / 스마트유통 /
   커스터마이징 / 외식 푸드테크 / 업사이클링 / 친환경포장.
   - 추가 소스: 네이버 뉴스 API(국내 핵심), 언론사 RSS, 학술은 CrossRef/PubMed API.
   - ✅ 안정성(결과 기반 폴백·재시도·헬스체크)은 T-001로 구현 완료.

3. **추적은 Resend 웹훅이 1차 수단.** (2026-07-11) ✅ T-003 구현 완료 — `POST /webhooks/resend`(svix
   서명 검증) → `engagement_events` 멱등 적재, clicked url=원본 기사 URL(캐시 매칭). 상세는 티켓.
   열람(open)은 프록시 오탐 때문에 보조 신호. 추적 도메인 `links.news.foodtech-center.org` Verified.

4. **발송은 4주차에 파일럿으로 조기 시작.** 완벽하지 않아도 시작해서 5·6·7주차 실데이터 누적.
   그 데이터로 Activity Score 가중치를 확정한다.
   파일럿 세그먼트는 **100명 이하**(2026-07-15) — Resend 무료 티어(일 100통) 한도 내, 본 발송 전 Pro($20/월) 전환.
   ✅ 2026-07-22: 발송 코드 완성(T-008)·푸디픽 #0 실발송·추적 관통 검증. **파일럿 대상 = 랩실**(교수님 결정,
   이메일 명단 추후 수령 → `pilot-lab` 프로그램 임포트). 발송 시점은 7/23 싱크에서.

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
   노션 archive에 키 평문 있음 — 워크스페이스가 민겸·희정 2인 전용이라 **로테이션 불필요 판단**(2026-07-15, 민겸).

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
    ✅ 배포 완료(2026-07-18, T-005) — 프로젝트 foodtech-hub, **계정은 교수님(snupfm@gmail.com)**.
    비용 전망: 파일럿까지 월 $5 → 본 발송 후 월 ~$25(Resend Pro $20 포함) — 상세는 노션 cost 페이지.
    트래킹 노션은 새 워크스페이스 "FoodTech-Agent"로 이전됨. **주차 진행 현황(Done/To do)은
    노션 `Project ▸ is on track` DB의 주차 페이지에 기록**(레포 docs 아님 — docs는 티켓·research용).
    시크릿은 노션에 평문 저장·복제 금지.

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
- **회원**: Supabase 3,413명(이메일 94%). 파일럿 `pilot-daily` 25명 = `pilot-lab-1`~`5` 각 5명
  (**A/B 그룹으로 그대로 쓸 수 있다**).
- **수집**: 네이버 `display` 100, 비대칭 캡(`MAX_DOMESTIC=120`/`MAX_OVERSEAS=40`), 분야 균형
  라운드로빈(`_cap_balanced`). 분류 프롬프트 v3(정부 공식 정의 삽입). **입력은 제목+요약 300자**
  (본문 스크래핑 안 함). 2차 게이트(`filter_foodtech_relevant`)는 발송 직전 LLM.
- **추적**: 추적 도메인 `links.news.foodtech-center.org`(Resend 추적 기본 OFF라 필수였음).
  clicked url = 원본 기사 URL — 이게 T-016에서 깨질 전제다.
- **`pilot_members`**(RLS): 25명 스냅샷+집계+Activity Score. `refresh_pilot_stats`가 발송 잡에서 롤업.

**T-009 기사 큐레이션(TODO)** — 소스 신뢰도·분야 다양성·중복 병합. 근거가 계속 쌓이는 중:
파일럿 #0의 쿠폰 기사 톱픽·지역지 모바일 불량, T-015의 튕김 절반, T-018에서 드러난
비뉴스 수집(`frontiersin.org`·`bentosushi.com`).

## 2026-08-04 세션 (파일럿 수신자 피드백 반영 — 전부 배포됨)

메일을 받아본 분들의 실제 피드백 6건에서 출발. 티켓 T-013~T-018로 배정.

- ✅ **T-013 뉴스레터 v2** — 아뮤즈부슈+에피3+메인2 → **에피2 + 메인3 + 디저트**(큐레이션 표준과 일치),
  **국내4:해외1**(해외는 메인에), 아뮤즈 자리에 "오늘의 분야" 줄. 디저트 = **원클릭 반응 3버튼**:
  `engagement_events`(`event_type="reacted"` + payload)라 스키마 변경 없고 (회원,편) 멱등이라 1행으로 수렴,
  토큰은 `member.unsubscribe_token` 재사용. 폭 600px → `max-width`(390px 잘림 해소). 시각 언어 = B안.
  헤더 아이콘 `app/static/foodie-icon.png`(네이비 `#042A4F`는 에셋 샘플값 — 변경 금지).
  **답장 버그도 함께 수정**: 발신 도메인에 MX가 없고 `reply_to`도 없어 푸터의 "답장하면 읽습니다"가
  거짓이었다 → `newsletter_reply_to`(운영값 = 교수님 지메일). **잔여: 실제 메일에서 답장 도달 확인.**
- ✅ **T-014 관리자 발송 설정** — `app_settings`(key/value JSONB, RLS) + 발송검토 탭 폼에서
  꼭지 수·국내외 비율·기간을 배포 없이 조정. **행이 없으면 코드 기본값**(마이그레이션 직후에도 발송 유지).
  수신자 상한 100은 일부러 설정에서 제외(결정 4 안전장치).
- ✅ **T-015 체류 근사** — 원문 체류는 측정 불가(남의 서버). **같은 편 안의 연속 클릭 간격**으로 근사
  (`dwell.py`, 30분 상한, 편별 마지막 클릭 제외). 인기분야 탭에 "읽은 깊이" 카드.
  운영 실측: 측정가능 47%, 중앙값 13초, **튕김 24 : 중간 23 : 정독 16** — 절반이 제목만 보고 닫는다(T-009 근거).
- ✅ **T-017 Activity Score** — 열람<클릭<반응 가중합 + 감쇠·축소·봇 제외. (별도 세션 작업물)
- ✅ **T-018 매체명** — `news_items` 460건 전부 `source`가 비어 있었다. 버그가 아니라 처음부터
  `fetch_naver`/`fetch_brave`가 `""`를 넣었고 RSS만 채웠는데 그게 폴백으로 밀린 탓. URL 호스트에서
  복원(`SOURCE_BY_DOMAIN` 55곳 + **도메인 폴백** — 모르면 지어내지 않는다). 460건 백필 완료.
- **T-016 착지 페이지 = 유일한 미착수.** 시안·A/B 설계 확정, 선결 질문 4개 중 3개 해결(티켓 참조).
  **미해결 = 이탈 비용** — `pilot-lab-1,2`(10명)만 착지 경유, 15명 직행으로 2주 A/B 하면 답이 나온다.
  까다로운 곳: 기사 링크를 수신자별로 바꿔야 하고(T-013의 "원본 URL 변형 금지"를 의도적으로 깸),
  그러면 T-003 매칭이 `engagement.py`·`pilot_daily.py`·`admin_pages.py` 3곳에서 2경로를 지원해야 한다.

**알아둘 것**: `/health/news`는 디스크 JSON 캐시를 본다 → **배포마다 빨간불**, 07:00 크론이 복구.
발송 조립은 DB(`news_items`)를 읽으므로 영향 없다 — 체크와 실제가 다른 걸 보는 상태.

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
