"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ASYNC_SCHEME = "postgresql+asyncpg://"


class Settings(BaseSettings):
    """Runtime configuration.

    Only variables that are actually used are defined here; more are added by the phase
    that first needs them (see docs/ARCHITECTURE.md, Configuration).
    """

    model_config = SettingsConfigDict(
        # `.env` in the working directory, then the repository-root `.env` when running
        # from `backend/`. Real environment variables always take priority.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation errors must never echo input values: DATABASE_URL contains a password.
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr
    cors_allowed_origins: str = "http://localhost:5173"
    github_token: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    # Gemini 2.5 Flash has been retired for new API users. This stable Flash Lite
    # alias remains broadly available and is suitable for grounded JSON responses.
    gemini_generation_model: str = "gemini-flash-lite-latest"
    embedding_model: str = "gemini-embedding-001"
    gemini_retry_attempts: int = 7
    github_http_timeout_seconds: float = 15
    max_tree_entries: int = 50000
    max_analyzed_files: int = 500
    max_file_size_bytes: int = 200000
    max_chunks_per_repository: int = 5000
    max_chunk_tokens: int = 800
    max_concurrent_analyses: int = 2
    retrieval_min_similarity: float = 0.45
    rate_limit_analyze: int = 10
    rate_limit_ask: int = 10
    rate_limit_read: int = 240

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        """Accept plain PostgreSQL URLs and select the asyncpg driver."""
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw, str):
            return value
        raw = raw.strip()
        for prefix in ("postgresql://", "postgres://"):
            if raw.startswith(prefix):
                raw = _ASYNC_SCHEME + raw[len(prefix) :]
        if not raw.startswith(_ASYNC_SCHEME):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+asyncpg://...)")
        return raw

    @model_validator(mode="after")
    def _reject_wildcard_cors_in_production(self) -> "Settings":
        if self.environment == "production" and "*" in self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain '*' in production")
        return self

    @property
    def cors_origins(self) -> list[str]:
        """CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are exposed in development only."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
