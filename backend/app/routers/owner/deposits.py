"""Owner API: preview the deposits a rule gives ("10% of the price"), worked out by the server."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth.supabase_auth import AuthUser
from app.routers.owner.deps import get_owner
from app.rules.deposits import SUGGESTED_PERCENT, deposit_for, minimum_for

router = APIRouter(prefix="/api/owner/deposits", tags=["owner: setup"])


class DepositPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(min_length=3, max_length=3)
    percent: Decimal | None = Field(default=None, ge=1, le=100)
    fixed: Decimal | None = Field(default=None, gt=0, le=100000)
    prices: list[Decimal] = Field(max_length=100)

    @model_validator(mode="after")
    def _one_rule(self) -> "DepositPreviewIn":
        if self.percent is not None and self.fixed is not None:
            raise ValueError("Choose a percent or a fixed amount, not both")
        return self


class DepositPreviewOut(BaseModel):
    deposits: list[Decimal]
    minimum: Decimal
    suggested_percent: Decimal


@router.post("/preview", response_model=DepositPreviewOut)
async def preview(data: DepositPreviewIn, owner: AuthUser = Depends(get_owner)):
    currency = data.currency.upper()
    percent = data.percent if data.fixed is None and data.percent is not None else (None if data.fixed else SUGGESTED_PERCENT)
    return DepositPreviewOut(
        deposits=[deposit_for(price=p, currency=currency, percent=percent, fixed=data.fixed) for p in data.prices],
        minimum=minimum_for(currency),
        suggested_percent=SUGGESTED_PERCENT,
    )
