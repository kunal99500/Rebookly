"""Owner API: see reviews, reply publicly, and report a review to Rebookly. Owners can't hide or edit reviews."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.review import OwnerReviewOut, ReplyIn, ReportIn, ReviewPage
from app.services import reviews

router = APIRouter(prefix="/api/owner/businesses/{business_id}/reviews", tags=["owner: reviews"])


@router.get("", response_model=ReviewPage)
async def list_reviews(offset: int = Query(default=0, ge=0, le=10_000),
                       business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return await reviews.page(session, business, offset, owner_view=True)


@router.put("/{review_id}/reply", response_model=OwnerReviewOut)
async def reply(review_id: uuid.UUID, data: ReplyIn, business: Business = Depends(get_owned_business),
                owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    """Add or change your public reply (shown under the review)."""
    return await reviews.reply(session, business, owner.id, review_id, data.text)


@router.delete("/{review_id}/reply", response_model=OwnerReviewOut)
async def remove_reply(review_id: uuid.UUID, business: Business = Depends(get_owned_business),
                       owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    return await reviews.reply(session, business, owner.id, review_id, None)


@router.post("/{review_id}/report", response_model=OwnerReviewOut)
async def report(review_id: uuid.UUID, data: ReportIn, business: Business = Depends(get_owned_business),
                 owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    """Ask Rebookly to look at a review (e.g. abusive or not about your business). It stays visible meanwhile."""
    return await reviews.report(session, business, owner.id, review_id, data.reason)