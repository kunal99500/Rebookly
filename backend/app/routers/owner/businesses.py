"""Owner API: create and manage businesses."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.business import BusinessCreate, BusinessOut, BusinessUpdate
from app.services import businesses

router = APIRouter(prefix="/api/owner/businesses", tags=["owner: businesses"])


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
async def create_business(
    data: BusinessCreate,
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Create a new business. It starts as a draft until PayPal is connected."""
    return await businesses.create_business(session, owner.id, data)


@router.get("", response_model=list[BusinessOut])
async def list_my_businesses(owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    """All businesses owned by the signed-in user."""
    return await businesses.list_owner_businesses(session, owner.id)


@router.get("/{business_id}", response_model=BusinessOut)
async def get_business(business: Business = Depends(get_owned_business)):
    return business


@router.patch("/{business_id}", response_model=BusinessOut)
async def update_business(
    data: BusinessUpdate,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Change only the fields that are sent."""
    return await businesses.update_business(session, business, owner.id, data)



@router.post("/{business_id}/go-live")
async def go_live(
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Open the business for bookings. If something required is missing, the answer lists exactly what."""
    from app.config import get_settings
    single_merchant = not get_settings().paypal_require_connected_account
    business = await businesses.go_live(session, business, owner.id, single_merchant)
    return {"status": business.status, "slug": business.slug}