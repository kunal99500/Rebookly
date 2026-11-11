"""Owner API: connect the business's own PayPal account."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.config import get_settings
from app.db import get_session
from app.models import Business
from app.payments.paypal import PayPalError
from app.routers.owner.deps import get_owned_business, get_owner, get_paypal
from app.schemas.paypal_connection import PayPalConnectionOut, PayPalConnectLink, PayPalConnectStart
from app.services import paypal_connection

router = APIRouter(prefix="/api/owner/businesses/{business_id}/paypal", tags=["owner: PayPal"])


def _partner_id() -> str:
    partner = get_settings().paypal_partner_merchant_id
    if not partner:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Connecting PayPal isn't set up on this server yet")
    return partner


@router.get("", response_model=PayPalConnectionOut)
async def connection(business: Business = Depends(get_owned_business)):
    return paypal_connection.connection_out(business)


@router.post("/connect", response_model=PayPalConnectLink)
async def connect(
    data: PayPalConnectStart,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    paypal=Depends(get_paypal),
    session: AsyncSession = Depends(get_session),
):
    """Get PayPal's sign-up link. Open it; PayPal sends you back to return_url when you're done."""
    _partner_id()
    if not data.return_url.startswith(get_settings().frontend_url.rstrip("/") + "/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "return_url must be a page of the Rebookly app")
    try:
        url = await paypal_connection.start(session, paypal, business, owner.id, data.return_url)
    except PayPalError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal isn't responding. Please try again.")
    return PayPalConnectLink(action_url=url)


@router.post("/refresh", response_model=PayPalConnectionOut)
async def refresh(
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    paypal=Depends(get_paypal),
    session: AsyncSession = Depends(get_session),
):
    """Check with PayPal: call this when the owner comes back from PayPal (and any time to recheck)."""
    try:
        return await paypal_connection.refresh(session, paypal, business, _partner_id(), owner.id)
    except PayPalError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal isn't responding. Please try again.")


@router.delete("", response_model=PayPalConnectionOut)
async def disconnect(
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    return await paypal_connection.disconnect(session, business, owner.id)