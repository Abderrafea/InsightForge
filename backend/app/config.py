from functools import lru_cache

from pydantic import Field, SecretStr
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

    @property
    def database_url(self) -> str:
        return self.app_database_url.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
