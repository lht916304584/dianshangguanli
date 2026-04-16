from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # LLM
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEFAULT_LLM_MODEL: str = "deepseek-chat"
    MAX_TITLE_LENGTH: int = 30
    DEFAULT_PLATFORM: str = "pinduoduo"

    # ── Project ──────────────────────────────────────────────────────
    PROJECT_NAME: str = "MyProject"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "FastAPI + PostgreSQL + Redis backend"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # ── API ──────────────────────────────────────────────────────────
    API_V1_STR: str = "/api/v1"
    ALLOWED_HOSTS: str = "*"
ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

@property
def ALLOWED_HOSTS_LIST(self) -> List[str]:
    v = self.ALLOWED_HOSTS.strip()
    if v.startswith("["):
        import json
        return json.loads(v)
    return [i.strip() for i in v.split(",") if i.strip()]

@property
def ALLOWED_ORIGINS_LIST(self) -> List[str]:
    v = self.ALLOWED_ORIGINS.strip()
    if v.startswith("["):
        import json
        return json.loads(v)
    return [i.strip() for i in v.split(",") if i.strip()]

    # ── Security ─────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24        # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ── Database ─────────────────────────────────────────────────────
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "appdb"
    POSTGRES_USER: str = "appuser"
    POSTGRES_PASSWORD: str = "apppassword"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Used by Alembic (sync driver)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── Celery ────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    def model_post_init(self, __context) -> None:
        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.REDIS_URL)
        if not self.CELERY_RESULT_BACKEND:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", self.REDIS_URL)

    # ── Email (optional) ──────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = "noreply@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
