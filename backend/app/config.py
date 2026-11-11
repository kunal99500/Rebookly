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
    paypal_partner_merchant_id: str = ""            # Rebookly's own PayPal merchant (account) ID
    paypal_require_connected_account: bool = False  # true in production: only connected businesses take bookings

    # ===== Supabase (Phase 2) =====
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    database_url: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")  # only for projects still on legacy HS256 tokens

    # ===== Data protection =====
    data_encryption_key: SecretStr = SecretStr("")  # one key, or several separated by commas (newest first)
    phone_hash_key: SecretStr = SecretStr("")

        # ===== AI =====
    llm_provider: str = "openai"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""                 # "smart" tier: onboarding, policy parsing, assistant
    llm_model_fast: str = ""            # "fast" tier: simple, cheap tasks (falls back to llm_model)
    ai_timeout_seconds: float = 30
    ai_max_output_tokens: int = 8000    # includes the model's reasoning; too low can mean empty replies

    # ===== AI monitoring (Langfuse) =====
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_capture_content: bool = True   # false = send timings and tokens only, no prompt text

        # ===== Location (geocoding) =====
    geocoder_base_url: str = "https://nominatim.openstreetmap.org"
    geocoder_api_key: SecretStr = SecretStr("")      # needed for paid providers such as LocationIQ
    geocoder_user_agent: str = "Rebookly/0.1 (contact: change-me@example.com)"
    geocoder_min_interval_seconds: float = 1.0      # Nominatim's public server: about 1 request per second
        # ===== Notifications (email) =====
    email_provider: Literal["console", "resend"] = "console"   # console = write emails to the log
    resend_api_key: SecretStr = SecretStr("")
    email_from: str = "Rebookly <onboarding@resend.dev>"


   
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