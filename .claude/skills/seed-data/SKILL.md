---
name: seed-data
description: 개발용 시드 데이터 투입. "/seed-data", "시드 넣어줘", "테스트 데이터" 요청 시 사용.
---

# /seed-data — 개발 시드 데이터

로컬 DB에 개발용 가짜 데이터를 넣는다.

## 절차

1. `docker compose up -d postgres` + `uv run alembic upgrade head` (스키마 최신화)
2. `uv run python scripts/seed.py`
   - 멱등: 이미 데이터가 있으면 스킵한다.
3. 확인: `uv run python -c "from sqlmodel import Session, select, func; from app.db import engine; from app.models import Member; print(Session(engine).exec(select(func.count()).select_from(Member)).one())"`

## 확장 규칙

- 새 도메인(뉴스레터, 이벤트 등) 시드가 필요하면 `scripts/seed.py`에 `seed_<도메인>()` 함수를 추가한다 (파일 분리 금지, 멱등 유지).
- 시드에 실제 회원 PII 사용 금지 — 반드시 가짜 데이터.
