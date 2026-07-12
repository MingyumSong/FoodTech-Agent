# C3: 순수 Postgres 기능만 사용

- Supabase 특화 기능(RLS, Supabase Auth, Storage, pg_cron, Edge Functions) 사용 금지.
- 이유: 최종적으로 기관 org로 이관 예정 — 어떤 Postgres 호스팅으로든 옮길 수 있어야 한다.
- DB 접근은 `DATABASE_URL` 하나로만. Supabase 클라이언트 SDK 도입 금지.
