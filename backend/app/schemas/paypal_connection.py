"""What the owner sees about their PayPal connection."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PayPalConnectStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_url: str = Field(max_length=500, description="Where PayPal sends the owner back (a page of our app)")


class PayPalConnectLink(BaseModel):
    action_url: str          # open this: PayPal's own sign-up / log-in pages


class PayPalConnectionOut(BaseModel):
    status: str              # not_connected, connected or needs_attention
    merchant_id_masked: str | None
    can_take_payments: bool
    problems: list[str]
    checked_at: datetime | None