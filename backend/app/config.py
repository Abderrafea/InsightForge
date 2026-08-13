from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "InsightForge API"
    app_env: str = "development"
    app_database_url: SecretStr
    secret_encryption_key: SecretStr
    external_db_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    query_max_rows: int = Field(default=1_000, ge=1, le=10_000)
    query_timeout_seconds: int = Field(default=10, ge=1, le=60)
    query_max_sql_length: int = Field(default=20_000, ge=100, le=100_000)
    query_max_joins: int = Field(default=8, ge=0, le=50)
    query_max_result_bytes: int = Field(default=1_000_000, ge=1_024, le=20_000_000)
    ai_provider: str = "groq"
    ai_model: str | None = None
    ai_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    ai_provider_timeout_seconds: int = Field(default=30, ge=1, le=120)
    ai_provider_max_retries: int = Field(default=2, ge=0, le=5)
    groq_api_key: SecretStr | None = None
    agent_max_sql_retries: int = Field(default=3, ge=0, le=10)
    agent_max_context_messages: int = Field(default=20, ge=1, le=100)
    agent_min_widgets: int = Field(default=2, ge=1, le=8)
    agent_max_widgets: int = Field(default=8, ge=2, le=12)
    agent_result_sample_rows: int = Field(default=5, ge=0, le=20)
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def database_url(self) -> str:
        return self.app_database_url.get_secret_value()

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_agent_limits(self) -> "Settings":
        if self.agent_min_widgets > self.agent_max_widgets:
            raise ValueError("AGENT_MIN_WIDGETS cannot exceed AGENT_MAX_WIDGETS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
