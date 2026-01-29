"""Application configuration management."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_name: str = "reemio-recommender"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # -------------------------------------------------------------------------
    # API Settings
    # -------------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # -------------------------------------------------------------------------
    # E-Commerce API Integration
    # -------------------------------------------------------------------------
    ecommerce_api_base_url: str = "https://gateway-ecommerce.reemioltd.com"
    ecommerce_api_key: str = ""
    ecommerce_api_timeout: int = 30

    # -------------------------------------------------------------------------
    # PostgreSQL Database
    # -------------------------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "reemio"
    postgres_password: str = ""
    postgres_db: str = "reemio_recommender"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Construct synchronous PostgreSQL connection URL (for Alembic)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # -------------------------------------------------------------------------
    # Vector Search (pgvector)
    # -------------------------------------------------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # -------------------------------------------------------------------------
    # Celery
    # -------------------------------------------------------------------------
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL, defaulting to Redis URL."""
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        """Get Celery result backend URL, defaulting to Redis URL."""
        return self.celery_result_backend or self.redis_url

    # -------------------------------------------------------------------------
    # Email Service
    # -------------------------------------------------------------------------
    email_service: Literal["mock", "sendgrid", "ses"] = "mock"
    email_from_address: str = "noreply@reemio.com"
    email_from_name: str = "Reemio"
    sendgrid_api_key: str = ""

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    secret_key: str = "change-me-in-production"
    api_key_header: str = "X-API-Key"

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20

    # -------------------------------------------------------------------------
    # Sync Worker Settings
    # -------------------------------------------------------------------------
    sync_products_interval_minutes: int = 60
    sync_orders_interval_minutes: int = 30

    # -------------------------------------------------------------------------
    # Recommendation Settings
    # -------------------------------------------------------------------------
    default_recommendation_limit: int = 12
    max_recommendation_limit: int = 50
    rerank_candidates_multiplier: int = 2
    attribution_window_days: int = 7

    # -------------------------------------------------------------------------
    # Email Campaign Settings
    # -------------------------------------------------------------------------
    cart_abandonment_delay_hours: int = 2
    cart_abandonment_max_reminders: int = 3
    weekly_digest_day: str = "sunday"
    weekly_digest_hour: int = 10


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
