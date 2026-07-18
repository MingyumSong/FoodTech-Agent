---
name: add-env
description: 새 환경변수(설정/시크릿) 추가 체크리스트. "/add-env KEY_NAME", "환경변수 추가", "키 추가" 요청 시 사용.
---

# /add-env — 환경변수 추가 루틴

새 설정값·시크릿은 터치포인트가 5곳이라 하나 빠지기 쉽다. 순서대로 전부 처리한다.

## 절차

1. **`app/config.py`** — `Settings`에 필드 추가 (snake_case, 기본값 `""` 또는 안전한 디폴트, 용도 주석).
2. **`.env.example`** — 키 이름 + 용도 주석 추가 (C6 규칙 의무. 실값 금지).
3. **`.env`** — 훅이 Claude의 편집을 차단하므로 **사용자에게 정확한 `KEY=값` 줄을 제시**하고 직접 추가 요청.
   시크릿 생성이 필요하면 `openssl rand -hex 32`로 만들어 제시.
4. **`scripts/railway-env-sync.sh`** — `--set "KEY=$KEY"` 줄 추가 (운영 배포에 필요한 키만.
   로컬 전용 설정이면 이 단계 생략하고 그 사실을 출력).
5. **반영**: 사용자에게 `! bash scripts/railway-env-sync.sh` 실행 요청 → 새 코드가 그 키를 읽으면
   `! railway up --service app --detach` 재배포까지. (둘 다 권한 분류기로 Claude 직접 실행 불가)
6. GitHub Actions 워크플로가 그 키를 쓰면 `gh secret set KEY`도 처리.

## 주의

- 시크릿 값을 로그·대화에 불필요하게 반복 출력하지 않는다 (생성 시 1회 제시만).
- `railway-env-sync.sh`의 완료 메시지 개수는 스크립트가 자동 계산한다 — 수동 갱신 불필요.
