# FoodTech Hub — 프로젝트 컨텍스트 (Claude Code용)

이 파일은 웹 채팅에서 논의한 내용을 터미널 세션으로 이어가기 위한 핸드오프 문서다.
Claude Code는 세션 시작 시 이 파일을 자동으로 읽는다. 200줄 이내로 유지할 것.

---

## 프로젝트 목표

푸드테크 기업인·연구자·재학생/졸업생으로 구성된 **약 100명 커뮤니티**(푸드테크 최고책임자과정 원우)의
회원 관리 + 주 1회 뉴스레터 자동 발송 + **참여 추적 → Activity Score → 활동/비활동 회원 분류**.
기간 8주(2026-07-06 ~ 08-29). 정례 싱크: 매주 목 16:00.

**프로젝트의 핵심 가치는 "추적 → 점수 → 분류"다.** 이게 아직 미구현이며 최우선이다.

---

## 현재 코드베이스 상태

- **스택**: FastAPI + SQLModel(ORM). DB는 로컬 SQLite(`data/foodtech.db`) / 운영 PostgreSQL(`DATABASE_URL`) 자동 전환.
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

## DB 테이블 (db.py)

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

1. **DB: 회원 명부는 Airtable로.** 100명 규모라 가벼운 Airtable가 적합.
   단, 발송·인증·추적 로직은 이 앱(SQL)에 남긴다. → **Airtable = 회원 원본 + 관리자 UI**,
   **앱 = 발송 + 추적 이벤트 기록**. 클릭 이벤트는 앱의 SQL에 쌓고 집계만 Airtable로 올린다.
   (Airtable API 5 req/초, 무료 1,200행 제한 주의)

2. **크롤링은 API/RSS 소스만.** HTML 스크래핑 제외.
   - 추가 소스: 네이버 뉴스 API(국내 핵심), 언론사 RSS, 학술은 CrossRef/PubMed API.
   - **안정성 수정 필수**: (a) Brave 한도초과/오류 시에도 RSS로 폴백되게 (현재는 키 부재 시에만 폴백),
     (b) 요청 재시도 + 백오프, (c) 발송 전 뉴스 수집 상태 헬스체크·알림.

3. **추적 로직에 역량 집중 (3주차 핵심).**
   - 클릭 추적: 리다이렉트 엔드포인트(`/r/{token}` → 원문 URL, 이벤트 기록 후 302).
   - 열람 추적: 픽셀(보조 신호로만).
   - 회원별·뉴스별 이벤트 테이블 신설 (member_id, newsletter_id, news_item, event_type, ts).

4. **발송은 4주차에 파일럿으로 조기 시작.** 완벽하지 않아도 시작해서 5·6·7주차 실데이터 누적.
   그 데이터로 Activity Score 가중치를 확정한다.

5. **Activity Score = 행동별 가중합.** 열람 < 클릭 < 전달 순으로 가중치.
   열람(open)은 Apple Mail/Gmail 프록시 때문에 신뢰도 낮음 → 보조 신호로만.
   **정밀 지표가 아니라 상대적 순위 도구**로 취급한다.

6. **대시보드는 자체 개발 대신 기존 BI.** Airtable Interfaces로 시작, 필요 시 Metabase.

---

## 추천 다음 작업 (우선순위 순)

1. 뉴스 수집 안정화: Brave→RSS 폴백 수정 + 재시도 + 발송전 헬스체크.
2. 추적 이벤트 테이블 + 클릭 리다이렉트 엔드포인트 + 열람 픽셀 구현.
3. Airtable 연동(회원 동기화) 설계.
4. Activity Score 산출 함수(가중치는 파라미터로) + Active/Dormant 분류 잡(job).

---

## 명령어

```bash
pip install -r requirements.txt
python app.py            # → http://localhost:8000
python import_members.py members.csv   # 회원 임포트
```

로컬 기본 DB는 SQLite라 API 키 없이도 뜬다. Brave/DART/Resend 키는 `.env`에 넣으면 활성화.
