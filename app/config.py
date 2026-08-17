from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://foodtech:foodtech@localhost:5432/foodtech"
    jobs_token: str = ""
    admin_token: str = ""  # 사람용 — 관리자 화면 전체를 연다
    # 기계용 — 참여도 CSV **조회만** 된다. 대시보드 연동(Cloudflare Pages)이 이걸 쓴다.
    # 사람 비번과 분리한 이유: 하나로 쓰면 연동에 발송 실행·회원 명단까지 넘어가고,
    # 사람 비번을 바꿀 때마다 연동이 끊긴다. 비어 있으면 이 경로는 비활성.
    scores_token: str = ""
    # **기본값이 prod 인 이유**: 개발 모드 판정이 이 값에 걸려 있다. 기본값을 local 로 두면
    # "환경변수를 안 넣은 배포"가 곧 무인증 공개가 된다(프리뷰 환경·새 서비스·env 초기화).
    # 부재를 열림으로 해석하지 않는다 — 개발 모드는 `scripts/dev.sh`가 APP_ENV=local 을
    # 명시적으로 넣을 때만 켜진다.
    app_env: str = "prod"

    @property
    def dev_mode(self) -> bool:
        """시크릿 없이 화면만 띄우는 모드 (T-027 4단계).

        랩실이 Events·Programs 섹션을 만들려면 화면이 떠야 하는데, 페이지 전체가 인증 뒤에
        있어서(결정 5) 계정이 없으면 아무것도 못 본다. 그렇다고 인증을 느슨하게 하면
        회원 3,400명과 발송 버튼이 열린다.

        **닫히는 쪽으로 실패한다**: 두 조건이 모두 맞아야 열린다.
          1. ADMIN_TOKEN 이 비어 있다 (운영엔 항상 있다)
          2. APP_ENV 가 개발 값이다 (운영은 prod 를 명시적으로 넣는다)
        둘 중 하나라도 어긋나면 기존대로 잠긴다.
        """
        return not self.admin_token and self.app_env in {"local", "dev", "test"}

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
