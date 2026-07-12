# C2: 스키마 변경은 반드시 Alembic 마이그레이션으로

- 모델(`app/models/`) 변경 시: `uv run alembic revision --autogenerate -m "설명"` → 생성된 파일 검토 → `uv run alembic upgrade head`.
- 운영/개발 DB에 `SQLModel.metadata.create_all` 사용 금지 (테스트 픽스처에서만 허용).
- 새 테이블 모델은 `app/models/__init__.py`에 임포트해야 autogenerate가 감지한다.
- 마이그레이션 파일은 수정하지 말고 새 리비전으로 전진한다 (이미 적용된 리비전 편집 금지).
- **새 테이블을 만드는 마이그레이션에는 `ALTER TABLE <이름> ENABLE ROW LEVEL SECURITY`를 함께 넣는다**
  (Supabase가 public 스키마를 PostgREST로 노출하므로 RLS 없인 Security Advisor 에러 + PII 노출 위험. T-002b 참고).
- autogenerate 산출물 검토 시 3종 함정 확인: ① 기존 행 있는 테이블의 NOT NULL 추가에 `server_default` 누락
  ② 이름 없는(`None`) 제약 → downgrade 불가 ③ 컬럼 drop 전 데이터 이관 부재.
