"""Client API: review a visit you attended."""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.schemas.review import MyReviewStatus, ReviewIn, ReviewOut
from app.services import clients, reviews

router = APIRouter(prefix="/api/client/bookings/{booking_id}/review", tags=["client: reviews"])


@router.get("", response_model=MyReviewStatus)
async def review_status(booking_id: uuid.UUID, user: AuthUser = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    """Your review of this visit (if any), and whether you can write or edit one."""
    return await reviews.my_status(session, await clients.require_client(session, user), booking_id)


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def write_review(booking_id: uuid.UUID, data: ReviewIn, user: AuthUser = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    """Rate a visit you attended (1-5 stars, optional comment), up to 30 days after it."""
    return await reviews.write(session, await clients.require_client(session, user), booking_id, data)


@router.patch("", response_model=ReviewOut)
async def edit_review(booking_id: uuid.UUID, data: ReviewIn, user: AuthUser = Depends(get_current_user),
                      session: AsyncSession = Depends(get_session)):
    """Change your review (for 7 days after writing it)."""
    return await reviews.edit(session, await clients.require_client(session, user), booking_id, data)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(booking_id: uuid.UUID, user: AuthUser = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    await reviews.delete(session, await clients.require_client(session, user), booking_id)