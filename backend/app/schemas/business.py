"""What the API accepts and returns for businesses. Validation happens here, before any database work."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.rules.catalog import CATEGORIES

Category = Literal[CATEGORIES]  # type: ignore[valid-type]


def _check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown time zone. Use a name like Europe/London or Asia/Kolkata.")
    return value


class BusinessCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: Category
    timezone: str = Field(default="UTC", max_length=64)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    capacity: int | None = Field(default=None, ge=1, le=500)
    _tz = field_validator("timezone")(_check_timezone)


class BusinessUpdate(BaseModel):
    """Every field optional: only what's sent is changed. Slug, status and PayPal fields can't be edited here."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: Category | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    privacy_mode: bool | None = None
    listed_publicly: bool | None = None
    vocabulary: dict[str, str] | None = None
    deposit_notice_timing: Literal["business_page", "booking_start", "checkout"] | None = None
    deposit_notice_note: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    notification_email: EmailStr | None = None
    deposit_notice_timing: Literal["business_page", "booking_start", "checkout"] | None = None
    deposit_notice_note: str | None = Field(default=None, max_length=160)
    capacity: int | None = Field(default=None, ge=1, le=500)
    @model_validator(mode="after")
    def _no_empty_required_fields(self) -> "BusinessUpdate":
        for field in ("name", "category", "timezone", "currency", "privacy_mode", "listed_publicly", "vocabulary"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty")
        return self

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        return None if value is None else _check_timezone(value)

    @field_validator("vocabulary")
    @classmethod
    def _vocab(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        allowed = {"booking", "client", "provider"}
        if not set(value) <= allowed or any(not 1 <= len(v) <= 30 for v in value.values()):
            raise ValueError("Vocabulary may only set booking, client and provider, each 1-30 characters")
        return value


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    slug: str
    category: str
    vocabulary: dict
    privacy_mode: bool
    timezone: str
    currency: str
    phone: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    listed_publicly: bool
    status: str
    paypal_status: str
    current_policy_version: int | None
    rating_average: Decimal | None
    rating_count: int
    created_at: datetime
    updated_at: datetime
    deposit_notice_timing: str
    deposit_notice_note: str | None