from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://foodtech:foodtech@localhost:5432/foodtech"
    jobs_token: str = ""
    app_env: str = "local"


settings = Settings()
