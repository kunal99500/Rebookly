"""Connecting a business's own PayPal account, so client payments go to the business directly.

Flow: the owner taps "Connect PayPal" -> PayPal's own pages (sign up or log in, give Rebookly permission)
-> back to our app -> we ask PayPal which account was connected and whether it can receive payments.
We never see the owner's PayPal password or bank details; PayPal handles all of that.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.models import Booking, Business, Payment
from app.payments.paypal import PayPalClient
from app.rules.paypal_onboarding import check_integration, tracking_id
from app.schemas.paypal_connection import PayPalConnectionOut
from app.services import audit

NOT_HEARD_YET = "We haven't heard from PayPal yet. If you've finished signing up, try again in a minute."


def _mask(merchant_id: str | None) -> str | None:
    return f"••••{merchant_id[-4:]}" if merchant_id else None


def connection_out(business: Business, problems: list[str] | None = None) -> PayPalConnectionOut:
    return PayPalConnectionOut(
        status=business.paypal_status, merchant_id_masked=_mask(business.paypal_merchant_id),
        can_take_payments=business.paypal_status == "connected",
        problems=problems or [], checked_at=business.paypal_checked_at,
    )


async def start(session: AsyncSession, paypal: PayPalClient, business: Business, owner_id: uuid.UUID,
                return_url: str) -> str:
    """Create PayPal's sign-up link for this business."""
    reference = tracking_id(business.id)
    action_url = await paypal.create_partner_referral(tracking_id=reference, return_url=return_url)
    business.paypal_tracking_id = reference
    audit.record(session, actor_type="owner", actor_id=owner_id, action="paypal.connect_started",
                 business_id=business.id, details={})
    await session.commit()
    return action_url


async def refresh(session: AsyncSession, paypal: PayPalClient, business: Business, partner_merchant_id: str,
                  owner_id: uuid.UUID | None = None) -> PayPalConnectionOut:
    """Ask PayPal which account is connected and whether it's ready. Never trusts the return page's address."""
    if not business.paypal_tracking_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start connecting PayPal first")
    merchant_id = business.paypal_merchant_id or await paypal.find_merchant_id(
        partner_merchant_id, business.paypal_tracking_id)
    if not merchant_id:
        return connection_out(business, [NOT_HEARD_YET])

    check = check_integration(await paypal.merchant_integration(partner_merchant_id, merchant_id))
    now = get_clock().now()
    was = business.paypal_status
    business.paypal_merchant_id, business.paypal_status, business.paypal_checked_at = merchant_id, check.status, now
    if check.status == "connected" and business.paypal_connected_at is None:
        business.paypal_connected_at = now
    if was != check.status:
        audit.record(session, actor_type="owner" if owner_id else "system", actor_id=owner_id,
                     action="paypal.status_changed", business_id=business.id,
                     details={"from": was, "to": check.status, "problems": list(check.problems)})
    await session.commit()
    return connection_out(business, list(check.problems))


async def disconnect(session: AsyncSession, business: Business, owner_id: uuid.UUID) -> PayPalConnectionOut:
    """Stop using this PayPal account. Not allowed while client deposits are still held on it."""
    held = await session.scalar(select(func.count()).select_from(Payment).join(Booking).where(
        Booking.business_id == business.id, Payment.kind == "hold",
        Payment.status.in_(("created", "authorized", "partially_captured"))))
    if held:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{held} client deposit(s) are still held on this PayPal account. "
                            "Disconnect after those bookings are finished.")
    business.paypal_merchant_id = business.paypal_tracking_id = None
    business.paypal_status, business.paypal_connected_at, business.paypal_checked_at = "not_connected", None, None
    audit.record(session, actor_type="owner", actor_id=owner_id, action="paypal.disconnected",
                 business_id=business.id, details={})
    await session.commit()
    return connection_out(business, ["To fully remove Rebookly's access, also revoke it in your PayPal settings."])