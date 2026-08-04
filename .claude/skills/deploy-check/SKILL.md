---
name: deploy-check
description: Railway 배포 후 검증 루틴. "/deploy-check", "배포 확인", "배포 검증", railway up 직후에 사용.
---

# /deploy-check — 배포 후 검증 루틴

운영 URL: `https://app-production-945c.up.railway.app` (CNAME 전까지)

## 먼저 — 스키마 변경이 있었나

**마이그레이션은 코드 배포보다 먼저 적용한다** (C2). 새 테이블/컬럼을 읽는 코드가 스키마보다
먼저 뜨면 조회가 즉시 실패한다. 이미 배포했는데 마이그레이션이 안 됐다면 지금 바로 적용한다.

## 절차

1. **빌드 완료까지 대기.** 고정 `sleep`은 짧으면 헛검증, 길면 낭비다. 상태를 폴링한다:
   ```bash
   for i in $(seq 1 40); do
     s=$(railway status 2>/dev/null | grep -m1 "status:")
     case "$s" in
       *Building*|*Deploying*|*Initializing*) sleep 10 ;;
       *) echo "배포 종료: $s"; break ;;
     esac
   done
   ```
2. **기본 검증**:
   ```bash
   B=https://app-production-945c.up.railway.app
   curl -s -m 15 "$B/health"; echo
   ```
   기대 `{"status":"ok","db":"ok"}`. 마이그레이션 포함 배포면
   `railway logs --service app | grep "Running upgrade"`로 리비전 적용도 확인.
3. **신 코드가 실제로 떴는지 판정** — 아래 "판정 신호" 참조. 여기가 틀리기 쉽다.
4. **부작용 없는 스모크**: 새 `/jobs/*`는 **토큰 없이** 호출해 401만 확인한다.
   정상 호출은 실발송·과금·중복적재를 일으키므로 금지.
5. 결과를 티켓 AC나 커밋 메시지에 기록.

## 판정 신호 — 상태 코드만 믿지 말 것

**기준은 "없는 라우트가 내는 응답과 구분되는가"이지 상태 코드 자체가 아니다.**

- **가장 확실한 단일 신호 — `/openapi.json`**: 공개로 200이고 모든 path가 들어 있다.
  인증·공개 라우트를 가리지 않으므로 새 엔드포인트 배포 여부는 이걸로 판정한다.
  ```bash
  curl -s "$B/openapi.json" | python3 -c "import sys,json;p=json.load(sys.stdin)['paths'];print([k for k in p if '새경로' in k] or '아직 없음')"
  ```
- **인증 라우트**: 미인증 호출이 404 → **401**로 바뀌면 라이브. 인증에서 막혀
  핸들러 본체가 실행되지 않으므로 안전하다.
- **공개 라우트**: ⚠️ **상태 코드로 판별 불가.** 없는 라우트도 404고 우리 핸들러가 거부해도
  404일 수 있다. **응답 본문**으로 갈라야 한다:
  - 없는 라우트 → `{"detail":"Not Found"}` (FastAPI 기본값)
  - 우리 핸들러 → `{"detail":"invalid token"}` 등 **우리가 쓴 문구**
- **기존 핸들러만 고친 배포**(새 경로 없음): 위 신호가 다 무력하다. 로그의 재시작 시각이나
  바뀐 응답 내용으로 확인한다.
- **정적 파일**: 200만 보지 말고 `%{content_type}`·`%{size_download}`까지 — 빈 응답을 놓친다.

## 주의

- 빌드가 안 끝나면 `railway logs`에서 원인을 찾는다. **추측 재배포 금지.**
- 시크릿 값은 출력하지 않는다. 시크릿 추가가 동반된 배포면 먼저 `/add-env` 확인.
- `/health/news`는 **디스크 JSON 캐시**를 본다 → 배포마다 파일이 날아가 빨간불이 뜬다.
  07:00 크론이 복구한다. 발송 조립은 DB(`news_items`)를 읽으므로 이것만으로 발송이 막히진 않는다.
