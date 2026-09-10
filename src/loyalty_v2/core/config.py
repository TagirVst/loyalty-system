from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LOYALTY_",
        extra="ignore",
    )

    app_name: str = "Loyalty System V2"
    environment: str = "development"
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/loyalty_v2")
    sql_echo: bool = False
    pin_fingerprint_secret: str = Field(default="change-me-in-production", min_length=16)
    pin_failures_before_lock: int = 5
    pin_base_lock_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
