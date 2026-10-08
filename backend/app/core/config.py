from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEROROUTE_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    openaq_api_key: SecretStr | None = None
    mapbox_token: SecretStr | None = None
    database_url: SecretStr | None = None
    aws_region: str | None = None
    s3_bucket: str | None = None

    @field_validator(
        "openaq_api_key", "mapbox_token", "database_url", "aws_region", "s3_bucket", mode="before"
    )
    @classmethod
    def blank_is_unconfigured(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
