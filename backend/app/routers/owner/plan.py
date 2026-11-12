"""Owner API: Rebookly's plans. Free (3% of money clients pay for visits) or Pro (monthly, no per-visit fee)."""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.config import get_settings
from app.db import get_session
from app.models import Booking, Business, Decision
from app.payments.subscriptions import SubscriptionError
from app.routers.owner.deps import get_owned_business, get_owner
from app.rules.plans import plan_from_paypal, pro_active
from app.rules.platform_fee import FREE_PLAN_RATE
from app.services import audit

router = APIRouter(prefix="/api/owner/businesses/{business_id}/plan", tags=["owner: plan"])


class PlanOut(BaseModel):
    plan: str                    # free or pro (what the owner is paying for)
    pro_active: bool
    pro_until: datetime | None
    fee_percent: Decimal         # Rebookly's fee on the free plan
    fees_this_month: Decimal     # Rebookly's fees taken this calendar month
    currency: str
    pro_price: str               # e.g. "₹499 a month"
    can_subscribe: bool          # Pro is set up on this server


class SubscribeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    return_url: str


class SubscribeOut(BaseModel):
    approve_url: str


def _subscriptions(request: Request):
    client = getattr(request.app.state, "subscriptions", None)
    if client is None or not get_settings().paypal_pro_plan_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The Pro plan isn’t available yet.")
    return client


async def _out(session: AsyncSession, business: Business) -> PlanOut:
    now = get_clock().now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fees = await session.scalar(select(func.coalesce(func.sum(Decision.platform_fee), 0)).join(Booking, Booking.id == Decision.booking_id)
                                .where(Booking.business_id == business.id, Decision.status == "executed",
                                       Decision.executed_at >= month_start))
    settings = get_settings()
    return PlanOut(plan=business.plan, pro_active=pro_active(business.plan, business.pro_until, now), pro_until=business.pro_until,
                   fee_percent=FREE_PLAN_RATE * 100, fees_this_month=Decimal(fees or 0), currency=business.currency,
                   pro_price=settings.pro_price_label, can_subscribe=bool(settings.paypal_pro_plan_id))


@router.get("", response_model=PlanOut)
async def current_plan(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return await _out(session, business)


@router.post("/subscribe", response_model=SubscribeOut)
async def subscribe(data: SubscribeIn, request: Request, business: Business = Depends(get_owned_business),
                    owner: AuthUser = Depends(get_owner), session: AsyncSession = Depends(get_session)):
    """Start a Pro subscription. The owner approves it on PayPal, then comes back and we check it."""
    settings = get_settings()
    if not data.return_url.startswith(settings.frontend_url.rstrip("/")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "return_url must be a Rebookly page")
    try:
        subscription_id, link = await _subscriptions(request).start(
            plan_id=settings.paypal_pro_plan_id, business_id=str(business.id),
            return_url=data.return_url, cancel_url=data.return_url)
    except SubscriptionError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal couldn’t start the subscription. Try again in a moment.")
    business.paypal_subscription_id = subscription_id
    audit.record(session, actor_type="owner", actor_id=owner.id, action="plan.subscribe_started", business_id=business.id,
                 details={"subscription": subscription_id})
    await session.commit()
    return SubscribeOut(approve_url=link)


@router.post("/refresh", response_model=PlanOut)
async def refresh(request: Request, business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    """Ask PayPal how the subscription stands. Never trusts the return page alone."""
    if business.paypal_subscription_id:
        try:
            paypal_status, next_billing = await _subscriptions(request).status(business.paypal_subscription_id)
        except SubscriptionError:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal didn’t answer. Try again in a moment.")
        business.plan = plan_from_paypal(paypal_status)
        if business.plan == "pro" and next_billing:
            business.pro_until = next_billing
        await session.commit()
    return await _out(session, business)


@router.post("/cancel", response_model=PlanOut)
async def cancel(request: Request, business: Business = Depends(get_owned_business), owner: AuthUser = Depends(get_owner),
                 session: AsyncSession = Depends(get_session)):
    """Stop Pro. It stays active until the end of the paid month, then the free plan applies."""
    if not business.paypal_subscription_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "There’s no Pro subscription to cancel.")
    try:
        await _subscriptions(request).cancel(business.paypal_subscription_id)
    except SubscriptionError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal couldn’t cancel it right now. Try again in a moment.")
    # Pro continues until the end of the month already paid for, then the free plan applies.
    business.plan = "pro" if business.pro_until and business.pro_until > get_clock().now() else "free"
    business.paypal_subscription_id = None
    audit.record(session, actor_type="owner", actor_id=owner.id, action="plan.cancelled", business_id=business.id, details={})
    await session.commit()
    return await _out(session, business)
