"""Application settings, loaded from backend/.env (or real environment variables).

Every other file gets settings through get_settings(); nothing reads os.environ directly.
Secrets are stored as SecretStr, so they show as ********** if printed or logged.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, found relative to this file so it works from any folder.
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE,
                                    env_file_encoding="utf-8",
                                    extra="ignore",
                                    hide_input_in_errors=True,)

    # ===== App =====
    app_env: Literal["development", "production"] = "development"
    frontend_url: str = "http://localhost:5000"
    backend_url: str = "http://localhost:8000"

    # ===== PayPal =====
    paypal_client_id: str = ""
    paypal_client_secret: SecretStr = SecretStr("")
    paypal_env: Literal["sandbox", "live"] = "sandbox"
    paypal_webhook_id: str = ""
    default_currency: str = "USD"

    # ===== Supabase (Phase 2) =====
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    database_url: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")  # only for projects still on legacy HS256 tokens

        # ===== Data protection =====
    data_encryption_key: SecretStr = SecretStr("")  # one key, or several separated by commas (newest first)
    phone_hash_key: SecretStr = SecretStr("")

    # ===== AI (Phase 3) =====
    llm_provider: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""

    # ===== Development only =====
    enable_dev_routes: bool = False
    simulated_clock: bool = False

    enable_jobs: bool = True  # background jobs (release unpaid bookings, recover payments)

    # ---------- validation ----------

    @field_validator("default_currency")
    @classmethod
    def _currency_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("DEFAULT_CURRENCY must be a 3-letter code like USD")
        return value

    @field_validator("frontend_url", "backend_url", "supabase_url")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def _safety_checks(self) -> "Settings":
        is_live = self.app_env == "production" or self.paypal_env == "live"
        if is_live and (self.enable_dev_routes or self.simulated_clock):
            raise ValueError(
                "ENABLE_DEV_ROUTES and SIMULATED_CLOCK must be false in production or with live PayPal"
            )

        if self.app_env == "production" and not (
            self.data_encryption_key.get_secret_value() and self.phone_hash_key.get_secret_value()
        ):
            raise ValueError("DATA_ENCRYPTION_KEY and PHONE_HASH_KEY are required in production")
        return self

    # ---------- helpers ----------

    @property
    def paypal_api_base(self) -> str:
        if self.paypal_env == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them everywhere."""
    return Settings()