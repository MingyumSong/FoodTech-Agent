---
name: migrate
description: Alembic 마이그레이션 생성·적용. 모델 변경 후 "/migrate", "마이그레이션 해줘", "스키마 반영" 요청 시 사용.
---

# /migrate — Alembic 마이그레이션

app/models/ 변경사항을 DB 스키마에 반영한다.

## 절차

1. 새 테이블 모델이면 `app/models/__init__.py`에 임포트됐는지 먼저 확인 (안 하면 autogenerate가 못 본다).
2. Postgres 기동 확인: `docker compose up -d postgres`
3. 리비전 생성:
   ```bash
   uv run alembic revision --autogenerate -m "변경 요약"
   ```
4. **생성된 `migrations/versions/*.py`를 반드시 열어 검토** — autogenerate는 테이블 rename을 drop+create로 오해하는 등 실수함.
5. 적용: `uv run alembic upgrade head`
6. 검증: `uv run pytest -q` (테스트는 metadata 기준이라 모델-마이그레이션 불일치 시 스키마 차이가 드러남)

## 금지

- 이미 적용된 리비전 파일 수정 (새 리비전으로 전진)
- `create_all`로 우회 (rules/alembic-migrations.md)
