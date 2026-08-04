from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://foodtech:foodtech@localhost:5432/foodtech"
    jobs_token: str = ""
    admin_token: str = ""  # 회원 API 잠금 (매직링크 로그인 전까지)
    app_env: str = "local"

    # 뉴스 수집 (T-001)
    naver_client_id: str = ""
    naver_client_secret: str = ""
    brave_search_api_key: str = ""
    news_cache_path: str = "data/news_cache.json"
    news_max_age_hours: int = 36  # 헬스체크: 캐시가 이보다 오래되면 stale
    news_min_items: int = 5  # 헬스체크: 캐시 items가 이보다 적으면 실패 신호

    # LLM (결정 7: OpenRouter 게이트웨이)
    openrouter_api_key: str = ""
    news_classify_model: str = "google/gemini-2.5-flash"  # T-004 드라이런으로 확정

    # 추적 (T-003) — Resend 웹훅 서명 검증 시크릿 (대시보드 웹훅 생성 시 발급, whsec_ 접두사)
    resend_webhook_secret: str = ""

    # 발송 (T-008) — 키 없으면 DRY RUN (실발송 없이 send_logs만 기록)
    resend_api_key: str = ""
    newsletter_from: str = "푸디 by 푸드테크센터 <foodie@news.foodtech-center.org>"  # 결정 10
    # 답장 수신 주소 (T-013). 발신 도메인엔 MX가 없어 답장이 반송되므로 실제 수신함을 지정한다.
    # 비우면 헤더를 생략 — 그 경우 답장은 어디에도 도달하지 않는다(푸터 문구도 함께 손볼 것).
    newsletter_reply_to: str = ""
    # 수신거부 링크 등 이메일 속 절대 URL의 베이스 (운영: Railway 도메인, CNAME 후 교체)
    public_base_url: str = "http://localhost:8000"


settings = Settings()
