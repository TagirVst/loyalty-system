from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOYALTY_", extra="ignore")

    app_name: str = "Loyalty System V2"
    environment: str = "development"
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/loyalty_v2")
    sql_echo: bool = False
    pin_fingerprint_secret: str = Field(default="change-me-in-production", min_length=16)
    identification_code_secret: str = Field(default="change-identification-secret", min_length=16)
    integration_api_key_secret: str = Field(default="change-integration-secret", min_length=16)
    pin_failures_before_lock: int = 5
    pin_base_lock_seconds: int = 300
    client_bot_token: str | None = None
    staff_bot_token: str | None = None
    organization_id: str | None = None

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment.lower() in {"production", "prod"}:
            if self.pin_fingerprint_secret == "change-me-in-production":
                raise ValueError("LOYALTY_PIN_FINGERPRINT_SECRET must be changed in production")
            if self.identification_code_secret == "change-identification-secret":
                raise ValueError("LOYALTY_IDENTIFICATION_CODE_SECRET must be changed in production")
            if self.integration_api_key_secret == "change-integration-secret":
                raise ValueError("LOYALTY_INTEGRATION_API_KEY_SECRET must be changed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
