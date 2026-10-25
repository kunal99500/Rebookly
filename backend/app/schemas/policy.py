"""What the API accepts and returns for cancellation policies."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FeeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["percent_of_hold", "fixed"]
    value: Decimal = Field(ge=0, le=100000, max_digits=8, decimal_places=2)


class PolicyRulesIn(BaseModel):
    """The structured policy, in the same shape the rules engine uses (the server assigns the version)."""
    model_config = ConfigDict(extra="forbid")

    free_cancel_hours: int
    late_cancel_fee: FeeIn
    no_show_fee: FeeIn
    waive_if_refilled: bool
    grace_minutes: int


class PolicyDraftIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    raw_text: str = Field(min_length=1, max_length=2000)  # the owner's own words
    rules: PolicyRulesIn


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    raw_text: str
    rules: dict
    confirmed_at: datetime | None
    created_at: datetime
    is_current: bool = False


class PreviewRow(BaseModel):
    situation: str
    outcome: str          # "No fee", "Fee: 10.00", "Applied to the price", ...
    charged: Decimal
    released: Decimal
    needs_owner_approval: bool
    reason: str


class PolicyPreviewOut(BaseModel):
    version: int
    example_hold: Decimal
    rules_note: str = "Calculated by the rules engine; this is exactly what will happen."
    rows: list[PreviewRow]
    warnings: list[str]