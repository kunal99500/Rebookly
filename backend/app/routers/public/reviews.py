"""Public API: a business's verified reviews."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Business
from app.routers.public.businesses import get_live_business
from app.schemas.review import ReviewPage
from app.services import reviews

router = APIRouter(prefix="/api/public/businesses", tags=["public"])


@router.get("/{slug}/reviews", response_model=ReviewPage)
async def business_reviews(offset: int = Query(default=0, ge=0, le=10_000),
                           business: Business = Depends(get_live_business),
                           session: AsyncSession = Depends(get_session)):
    """Newest first, 20 at a time, with the rating summary. Every review comes from an attended visit."""
    return await reviews.page(session, business, offset)