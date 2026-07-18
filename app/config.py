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


settings = Settings()
