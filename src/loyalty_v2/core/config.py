from functools import lru_cache
from uuid import UUID

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
    def validate_runtime_configuration(self):
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("LOYALTY_DATABASE_URL must use postgresql+asyncpg")
        if self.organization_id is not None:
            try:
                UUID(self.organization_id)
            except ValueError as exc:
                raise ValueError("LOYALTY_ORGANIZATION_ID must be a valid UUID") from exc
        if self.environment.lower() in {"production", "prod"}:
            secrets = {
                "LOYALTY_PIN_FINGERPRINT_SECRET": self.pin_fingerprint_secret,
                "LOYALTY_IDENTIFICATION_CODE_SECRET": self.identification_code_secret,
                "LOYALTY_INTEGRATION_API_KEY_SECRET": self.integration_api_key_secret,
            }
            defaults = {"change-me-in-production", "change-identification-secret", "change-integration-secret"}
            for name, value in secrets.items():
                if value in defaults or len(value) < 32:
                    raise ValueError(f"{name} must be a unique secret with at least 32 characters in production")
            if len(set(secrets.values())) != len(secrets):
                raise ValueError("Production security secrets must be different from each other")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
