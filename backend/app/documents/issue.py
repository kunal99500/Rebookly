"""Issues documents at the moments that matter:

  booking confirmed            -> booking confirmation (with the check-in QR code)
  attended, hold captured      -> payment receipt
  fee captured                 -> fee receipt
  hold released (any reason)   -> release notice

Issuing is idempotent: calling it twice for the same moment never creates a second document.
Documents are frozen once saved (the database refuses edits).
"""
import logging
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.compliance import profiles as tax_profiles
from app.compliance.countries import get_pack
from app.compliance.tax import receipt_tax_section, tax_for_price

from app.clock import get_clock
from app.config import get_settings
from app.documents.schemas import DocumentLinkOut
from app.documents.snapshots import TITLES, build_snapshot, document_number, document_type_for
from app.models import Booking, BookingItem, Business, Client, Decision, Document, Payment, Staff, Service
from app.rules.engine import Policy
from app.rules.formatting import local_time
from app.rules.outcomes import masked_last4
from app.rules.policy_text import policy_summary

logger = logging.getLogger("rebookly.documents")


async def _context(session: AsyncSession, booking: Booking) -> dict:
       """Gather everything a document shows, as plain values."""
       business = await session.get(Business, booking.business_id)
       client = await session.get(Client, booking.client_id)
       item_names = list(await session.scalars(
           select(BookingItem.name).where(BookingItem.booking_id == booking.id).order_by(BookingItem.position)))
       staff = (await session.scalar(select(Staff.name).where(Staff.id == booking.staff_id))
                if booking.staff_id else None)
       payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id, Payment.kind == "hold"))
       policy = Policy.from_dict({**booking.policy_snapshot, "version": booking.policy_version})
       tz = business.timezone
       return {
           "business": {"name": business.name, "address": business.address, "phone": business.phone, "timezone": tz},
           "client": {"name": client.name, "phone_masked": masked_last4(client.phone_last4),
                      "attendee": booking.attendee_name},
           "booking": {
               "confirmation_number": booking.confirmation_number,
               "service": " + ".join(item_names) or "Booking",
               "staff": staff,
               "duration_minutes": int((booking.ends_at - booking.starts_at).total_seconds() // 60),
               "when": local_time(booking.starts_at, tz),
               "payment_option": booking.payment_option, "price": str(booking.price),
               "held": str(booking.held_amount), "currency": booking.currency,
               "check_in_token": booking.check_in_token,
           },
           "payment": {
               "method": payment.method if payment else None,
               "card_brand": payment.card_brand if payment else None,
               "card_last_digits": payment.card_last_digits if payment else None,
               "paypal_order_id": payment.paypal_order_id if payment else None,
           },
           "policy": {
               "version": policy.version,
               "lines": policy_summary(policy),
               "free_until": local_time(booking.starts_at - timedelta(hours=policy.free_cancel_hours), tz)
               if policy.free_cancel_hours else None,
           },
           "timezone": tz,
       }

async def _tax_section(session: AsyncSession, booking: Booking, doc_type: str, charged: Decimal) -> dict | None:
       """The tax block for this document, or None. Release notices never show tax (nothing was charged)."""
       if doc_type == "release_notice":
           return None
       profile = await tax_profiles.get_profile(session, booking.business_id)
       registration = {
           "registration_label": get_pack(profile.country_code).registration_label if profile else None,
           "registration_number": profile.registration_number if profile else None,
           "legal_name": profile.legal_name if profile else None,
       }
       if doc_type == "fee_receipt":
           # Only if the owner has said fees are taxable; a fee is a final amount, so the tax is inside it.
           if not (profile and profile.tax_registered and profile.fees_taxable and profile.tax_rate is not None):
               return None
           line = tax_for_price(Decimal(charged), profile.tax_rate, prices_include_tax=True)
           return receipt_tax_section(label=profile.tax_label, rate=profile.tax_rate, prices_include_tax=True,
                                      amount=line.tax, currency=booking.currency, **registration)
       items = [i for i in await session.scalars(select(BookingItem).where(BookingItem.booking_id == booking.id))
                if i.tax_rate is not None]
       if not items:
           return None
       return receipt_tax_section(
           label=profile.tax_label if profile else "Tax", rate=items[0].tax_rate,
           prices_include_tax=bool(items[0].price_includes_tax), amount=sum(i.tax_amount for i in items),
           currency=booking.currency, on_visit_total=True, **registration,
       )

async def _save(session: AsyncSession, booking: Booking, doc_type: str, source: Decision | None,
                replaces: Document | None = None, **extra) -> Document:
    sequence = 1 + await session.scalar(select(func.count()).select_from(Document).where(
        Document.booking_id == booking.id, Document.type == doc_type))
    number = document_number(booking.confirmation_number, doc_type, sequence)
    now = get_clock().now()
    context = await _context(session, booking)
    tax = await _tax_section(session, booking, doc_type, extra.get("charged", Decimal("0")))
    snapshot = build_snapshot(
           doc_type, number=number, issued_at=now, issued_local=local_time(now, context["timezone"]),
           business=context["business"], client=context["client"], booking=context["booking"],
           payment=context["payment"], policy=context["policy"], tax=tax, **extra,
       )
    document = Document(
        id=uuid.uuid4(), business_id=booking.business_id, booking_id=booking.id,
        decision_id=source.id if source else None, type=doc_type, number=number,
        snapshot=snapshot, access_token=secrets.token_urlsafe(32),
        replaces_document_id=replaces.id if replaces else None,
    )
    session.add(document)
    await session.flush()
    return document


async def issue_confirmation(session: AsyncSession, booking: Booking, replace: bool = False) -> Document:
       """The booking confirmation. With replace=True (after a move), a new one is issued for the new time."""
       existing = await session.scalar(
           select(Document).where(Document.booking_id == booking.id, Document.type == "booking_confirmation")
           .order_by(Document.issued_at.desc()).limit(1))
       if existing is not None and not replace:
           return existing
       return await _save(session, booking, "booking_confirmation", None, replaces=existing)


async def issue_for_decision(session: AsyncSession, decision: Decision) -> Document | None:
    if decision.status not in ("executed", "waived"):
        return None
    existing = await session.scalar(select(Document).where(Document.decision_id == decision.id))
    if existing is not None:
        return existing
    booking = await session.get(Booking, decision.booking_id)
    doc_type = document_type_for(decision.event, decision.action, decision.final_amount)
    return await _save(session, booking, doc_type, decision, charged=decision.final_amount or 0,
                       decision={"reason": decision.reason, "rule": decision.rule})


async def list_for_booking(session: AsyncSession, booking_id: uuid.UUID) -> list[DocumentLinkOut]:
    base = get_settings().backend_url
    rows = await session.scalars(select(Document).where(Document.booking_id == booking_id).order_by(Document.issued_at))
    return [DocumentLinkOut(type=d.type, title=TITLES[d.type], number=d.number, issued_at=d.issued_at,
                            url=f"{base}/documents/{d.access_token}") for d in rows]


async def issue_safely(session: AsyncSession, issuing) -> None:
    """Issue a document inside a savepoint: if it fails, the booking and payment are still saved."""
    try:
        async with session.begin_nested():
            await issuing
    except Exception:
        logger.exception("Couldn't issue a document; it can be issued again later")