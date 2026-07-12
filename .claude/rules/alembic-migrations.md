# C2: 스키마 변경은 반드시 Alembic 마이그레이션으로

- 모델(`app/models/`) 변경 시: `uv run alembic revision --autogenerate -m "설명"` → 생성된 파일 검토 → `uv run alembic upgrade head`.
- 운영/개발 DB에 `SQLModel.metadata.create_all` 사용 금지 (테스트 픽스처에서만 허용).
- 새 테이블 모델은 `app/models/__init__.py`에 임포트해야 autogenerate가 감지한다.
- 마이그레이션 파일은 수정하지 말고 새 리비전으로 전진한다 (이미 적용된 리비전 편집 금지).
