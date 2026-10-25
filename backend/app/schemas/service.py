"""What the API accepts and returns for services (what a business sells)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PaymentOption = Literal["deposit_held", "full_held"]
Money = Field(ge=0, le=100000, max_digits=8, decimal_places=2)


def _clean_options(options: list[str]) -> list[str]:
    if not options:
        raise ValueError("Choose at least one payment option")
    if len(set(options)) != len(options):
        raise ValueError("Each payment option can only be listed once")
    return options


class ServiceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int = Field(ge=5, le=720)
    price: Decimal = Money
    deposit: Decimal = Money
    payment_options: list[PaymentOption] = Field(default_factory=lambda: ["deposit_held"])
    sort_order: int = Field(default=0, ge=0, le=1000)

    _options = field_validator("payment_options")(_clean_options)

    @model_validator(mode="after")
    def _check_money(self) -> "ServiceCreate":
        check_service_money(self.price, self.deposit, self.payment_options)
        return self


class ServiceUpdate(BaseModel):
    """Every field optional. Money rules are re-checked against the merged result in the service layer."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int | None = Field(default=None, ge=5, le=720)
    price: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=8, decimal_places=2)
    deposit: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=8, decimal_places=2)
    payment_options: list[PaymentOption] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None

    @field_validator("payment_options")
    @classmethod
    def _options(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_options(value)

    @model_validator(mode="after")
    def _no_empty_required_fields(self) -> "ServiceUpdate":
        for field in ("name", "duration_minutes", "price", "deposit", "payment_options", "sort_order", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty")
        return self


def check_service_money(price: Decimal, deposit: Decimal, payment_options: list[str]) -> None:
    """Rules every service must follow, on create and after every update."""
    if deposit > price:
        raise ValueError("The deposit can't be more than the price")
    if "deposit_held" in payment_options and deposit <= 0:
        raise ValueError("Set a deposit above zero to offer the 'deposit held' option")
    if "full_held" in payment_options and price <= 0:
        raise ValueError("Set a price above zero to offer the 'full amount held' option")


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    description: str | None
    duration_minutes: int
    price: Decimal
    deposit: Decimal
    payment_options: list[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime