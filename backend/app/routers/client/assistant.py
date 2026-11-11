"""Client API: the booking assistant chat."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.assistant import AssistantOut, AssistantRequest, RateLimiter, chat
from app.ai.client import AIUnavailable
from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business
from app.services import clients
from app.services.assistant_tools import DbClientTools

router = APIRouter(prefix="/api/client", tags=["client: assistant"])
limiter = RateLimiter()


@router.post("/assistant", response_model=AssistantOut)
async def assistant(
    data: AssistantRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Chat about your bookings. Changes come back as `actions` for you to confirm; nothing changes until then.

    Send the whole conversation each time (up to 20 messages), ending with the client's message.
    To confirm an action, call the normal endpoint: POST /bookings/{id}/reschedule or /bookings/{id}/cancel.
    """
    ai = getattr(request.app.state, "ai", None)
    if ai is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The assistant isn't available right now")
    if data.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The last message must be from you")
    if not limiter.allow(str(user.id)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "You've sent a lot of messages. Please try again in a little while.")
    client = await clients.require_client(session, user)

    business = None
    if data.business_slug:
        business = await session.scalar(select(Business).where(
            Business.slug == data.business_slug, Business.status == "live"))
    timezone = data.timezone or (business.timezone if business else "UTC")
    try:
        return await chat(ai, DbClientTools(session, client), data, client_name=client.name,
                          timezone=timezone, business_name=business.name if business else None)
    except AIUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The assistant isn't responding. You can still manage bookings under My bookings.")