"""Dependencies for owner routes: who the owner is, and which business they may manage."""
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business


async def get_owner(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Any signed-in, non-anonymous user can act as an owner of their own businesses."""
    if user.is_anonymous:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with your account to manage a business")
    return user


async def get_owned_business(
    business_id: uuid.UUID,
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
) -> Business:
    """Load a business only if the signed-in user owns it.

    Returns 404 (not 403) for other people's businesses, so the API never reveals which IDs exist.
    """
    business = await session.get(Business, business_id)
    if business is None or business.owner_user_id != owner.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business

def get_paypal(request: Request):
    """The shared PayPal client, or a clear error if payments aren't configured."""
    paypal = getattr(request.app.state, "paypal", None)
    if paypal is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Payments are not available right now")
    return paypal