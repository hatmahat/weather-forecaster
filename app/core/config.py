from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ML Service API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str
    SQLALCHEMY_ECHO: bool = False

    # CORS (comma-separated list of origins)
    CORS_ORIGINS: str = "*"

    # Logging
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    LOG_FILE: Optional[str] = None

    # AWS S3 Configuration
    AWS_S3_ACCESS_KEY: Optional[str] = None
    AWS_S3_SECRET_KEY: Optional[str] = None
    AWS_S3_REGION: str = "us-east-1"
    AWS_S3_BUCKET_NAME: str
    AWS_S3_PRESIGNED_URL_DURATION_MINUTES: int = 15
    AWS_S3_USE_IAM_ROLE: bool = True

    # Webhook: notify a downstream service when a job completes
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_API_KEY: Optional[str] = None
    WEBHOOK_ENABLED: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
