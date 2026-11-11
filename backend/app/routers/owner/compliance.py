"""Owner API: the business's tax details, as printed on receipts."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.compliance import profiles
from app.compliance.schemas import TaxProfileIn, TaxProfileOut
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner

router = APIRouter(prefix="/api/owner/businesses/{business_id}/tax-profile", tags=["owner: tax"])


@router.get("", response_model=TaxProfileOut)
async def get_tax_profile(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    profile = await profiles.get_profile(session, business.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tax details yet")
    return profiles.to_out(profile, business.region_code)


@router.put("", response_model=TaxProfileOut)
async def save_tax_profile(
    data: TaxProfileIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Save tax details. New bookings use them from now on; existing bookings and receipts don't change."""
    return profiles.to_out(await profiles.save_profile(session, business, owner.id, data), business.region_code)