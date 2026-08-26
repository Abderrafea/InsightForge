from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
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
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    agent_max_sql_retries: int = Field(default=3, ge=0, le=10)
    agent_max_context_messages: int = Field(default=20, ge=1, le=100)
    agent_min_widgets: int = Field(default=2, ge=1, le=8)
    agent_max_widgets: int = Field(default=8, ge=2, le=12)
    agent_result_sample_rows: int = Field(default=5, ge=0, le=20)
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_origin: str | None = None
    access_proxy_token: SecretStr | None = None
    external_db_allowed_targets: str = ""
    max_request_bytes: int = Field(default=65_536, ge=1_024, le=1_000_000)
    max_concurrent_requests: int = Field(default=8, ge=1, le=64)
    access_mode: Literal["owner", "public"] = "owner"
    deployment_mode: Literal["gateway", "render", "direct"] = "gateway"
    frontend_dist_dir: str | None = None
    visitor_cleanup_interval_seconds: int = Field(default=3600, ge=60, le=86400)
    app_db_pool_size: int = Field(default=3, ge=1, le=10)
    visitor_session_hours: int = Field(default=8, ge=1, le=24)
    max_visitors: int = Field(default=1000, ge=1, le=10000)
    visitor_models: str = "openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b"
    visitor_openai_models: str = "gpt-6-luna,gpt-6.1-sol,gpt-6-astra"
    visitor_anthropic_models: str = "claude-sonnet-5-5,claude-haiku-5-5"
    visitor_allow_custom_models: bool = True

    @property
    def visitor_providers(self) -> list[dict]:
        return [
            {"id": "groq", "label": "Groq", "models": self.allowed_visitor_models},
            {
                "id": "openai",
                "label": "OpenAI (GPT)",
                "models": self.visitor_openai_models.split(","),
            },
            {
                "id": "anthropic",
                "label": "Anthropic (Claude)",
                "models": self.visitor_anthropic_models.split(","),
            },
        ]

    @property
    def public_visitors(self) -> bool:
        return self.access_mode == "public"

    @property
    def allowed_visitor_models(self) -> list[str]:
        return [model.strip() for model in self.visitor_models.split(",") if model.strip()]

    @property
    def production(self) -> bool:
        return self.app_env.casefold() == "production"

    @property
    def allowed_database_targets(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.external_db_allowed_targets.split(",")
            if item.strip()
        }

    @property
    def database_url(self) -> str:
        return self.app_database_url.get_secret_value()

    @property
    def allowed_origins(self) -> list[str]:
        if self.production:
            return [self.public_origin.rstrip("/")] if self.public_origin else []
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_agent_limits(self) -> "Settings":
        if self.agent_min_widgets > self.agent_max_widgets:
            raise ValueError("AGENT_MIN_WIDGETS cannot exceed AGENT_MAX_WIDGETS")
        if self.app_env.casefold() not in {"development", "testing", "production"}:
            raise ValueError("APP_ENV must be development, testing or production")
        if self.production:
            origin = urlsplit(self.public_origin or "")
            if (
                origin.scheme != "https"
                or not origin.hostname
                or "*" in origin.hostname
                or origin.username
                or origin.password
                or origin.path not in {"", "/"}
                or origin.query
                or origin.fragment
            ):
                raise ValueError("PUBLIC_ORIGIN must be a single HTTPS origin")
            token = self.access_proxy_token.get_secret_value() if self.access_proxy_token else ""
            if self.deployment_mode == "gateway" and len(token) < 32:
                raise ValueError("ACCESS_PROXY_TOKEN must contain at least 32 characters")
            if self.deployment_mode in {"render", "direct"} and not self.public_visitors:
                raise ValueError("Direct deployment requires isolated public visitor mode")
            key = self.secret_encryption_key.get_secret_value()
            if key == "7B1wI_gfTi94x_6crw4VBbg4FPVkudmkx5zeO0oBHho=":
                raise ValueError("Production requires a unique SECRET_ENCRYPTION_KEY")
            try:
                Fernet(key)
            except (ValueError, TypeError) as exc:
                raise ValueError("SECRET_ENCRYPTION_KEY must be a Fernet key") from exc
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires a PostgreSQL app database")
            if "insightforge_dev" in self.database_url:
                raise ValueError("Production cannot use the development database password")
            if not self.public_visitors and not self.allowed_database_targets:
                raise ValueError("EXTERNAL_DB_ALLOWED_TARGETS is required in production")
            configured_key = {
                "groq": self.groq_api_key,
                "openai": self.openai_api_key,
                "anthropic": self.anthropic_api_key,
            }.get(self.ai_provider.casefold())
            if not self.public_visitors and (
                not self.ai_model
                or not self.ai_model.strip()
                or not configured_key
                or not configured_key.get_secret_value().strip()
            ):
                raise ValueError("Production requires AI_MODEL and the selected provider's API key")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
