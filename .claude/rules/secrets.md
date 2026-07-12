# C6: 시크릿 관리

- API 키/DB URI/토큰 하드코딩 금지. 설정은 `app/config.py`의 `Settings`를 통해서만 읽는다.
- 새 설정값 추가 시 `.env.example`에 키 이름과 용도 주석을 반드시 추가한다.
- `.env`는 gitignore 대상 — 커밋 금지, 로그에 시크릿 출력 금지.
- 회원 PII(이름·이메일·전화)는 로그에 남기지 않는다.
