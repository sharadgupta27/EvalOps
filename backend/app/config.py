"""Application settings. The only module allowed to read environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-only-change-me-0123456789abcdef"  # noqa: S105  (rejected in prod)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite+aiosqlite:///./evalops.db"
    sql_echo: bool = False

    jwt_secret: SecretStr = SecretStr(_DEV_JWT_SECRET)
    jwt_expire_minutes: int = 60 * 12
    # bcrypt work factor. Tests lower it to 4 for speed; never lower it in prod.
    bcrypt_rounds: int = 12
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # LLM
    llm_provider: Literal["fake", "anthropic"] = "fake"
    anthropic_api_key: SecretStr | None = None
    default_model: str = "claude-opus-5-5"
    judge_model: str = "claude-opus-5-5"
    judge_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = "low"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3

    # Worker and guardrails
    worker_concurrency: int = 4
    worker_poll_seconds: float = 1.0
    max_cases_per_run: int = 200
    max_cost_per_run_usd: float = 2.0
    # Per project, per UTC day. Stops a looping agent or leaked key from queuing run after run.
    max_daily_cost_usd: float = 20.0
    max_upload_bytes: int = 2 * 1024 * 1024

    # Demo account created by `python -m app.seed`. Public demo only; never a real account.
    demo_password: SecretStr = SecretStr("evalops-demo-2026")

    # Abuse protection
    rate_limit_per_minute: int = 120

    # Observability
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "evalops-api"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _prod_safety(self) -> "Settings":
        if self.environment == "prod":
            if (
                self.jwt_secret.get_secret_value() == _DEV_JWT_SECRET
                or len(self.jwt_secret.get_secret_value()) < 32
            ):
                raise ValueError("JWT_SECRET must be set to a random value of 32+ chars in prod")
            if self.bcrypt_rounds < 12:
                raise ValueError("BCRYPT_ROUNDS must be >= 12 in prod")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
