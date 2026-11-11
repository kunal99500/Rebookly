"""Owner API: where the business is."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.geo.schemas import BusinessLocationIn, BusinessLocationOut
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.services import locations

router = APIRouter(prefix="/api/owner/businesses/{business_id}/location", tags=["owner: location"])


@router.get("", response_model=BusinessLocationOut)
async def get_location(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return await locations.location_out(session, business)


@router.put("", response_model=BusinessLocationOut)
async def set_location(
    data: BusinessLocationIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Save the business's address and map position (from live location, a search result, or typed by hand)."""
    return await locations.set_location(session, business, owner.id, data)