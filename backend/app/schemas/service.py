"""What the API accepts and returns for services (what a business sells)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PaymentOption = Literal["deposit_held", "full_held"]
ServiceKind = Literal["main", "add_on"]          # add-ons (e.g. hair wash) are only booked with a main service
BookingMode = Literal["appointment", "class"]    # appointment: times calculated; class: fixed sessions with seats
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
    kind: ServiceKind = "main"
    booking_mode: BookingMode = "appointment"
    duration_minutes: int = Field(ge=5, le=720)
    cleanup_minutes: int = Field(default=0, ge=0, le=240, description="Free time kept after the visit")
    price: Decimal = Money
    deposit: Decimal = Money
    payment_options: list[PaymentOption] = Field(default_factory=lambda: ["deposit_held"])
    sort_order: int = Field(default=0, ge=0, le=1000)

    _options = field_validator("payment_options")(_clean_options)

    @model_validator(mode="after")
    def _check_money(self) -> "ServiceCreate":
        check_service_money(self.price, self.deposit, self.payment_options, self.kind)
        return self


class ServiceUpdate(BaseModel):
    """Every field optional. Money rules are re-checked against the merged result in the service layer."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    kind: ServiceKind | None = None
    booking_mode: BookingMode | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=720)
    cleanup_minutes: int | None = Field(default=None, ge=0, le=240)
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
        for field in ("name", "kind", "booking_mode", "duration_minutes", "cleanup_minutes", "price", "deposit",
                      "payment_options", "sort_order", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty")
        return self


def check_service_money(price: Decimal, deposit: Decimal, payment_options: list[str], kind: str = "main") -> None:
    """Rules every service must follow, on create and after every update."""
    if deposit > price:
        raise ValueError("The deposit can't be more than the price")
    if kind == "add_on":
        return  # add-ons follow the payment option of the main service they're booked with
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
    kind: str
    booking_mode: str
    duration_minutes: int
    cleanup_minutes: int
    price: Decimal
    deposit: Decimal
    payment_options: list[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime