"""Business logic for cancellation policies: drafts, previews and confirmation.

Policies are versioned. A draft can be previewed and confirmed; once confirmed it never changes.
New bookings use the business's current confirmed version.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.catalog import BOOKING_WINDOW_HOURS
from app.clock import get_clock
from app.models import Business, BusinessPolicy, Service
from app.rules.engine import Action, BookingFacts, Event, FeeKind, Policy, decide
from app.schemas.policy import PolicyDraftIn, PolicyPreviewOut, PreviewRow
from app.services import audit

DEFAULT_EXAMPLE_HOLD = Decimal("20.00")


def to_engine_policy(rules: dict, version: int) -> Policy:
    """Turn stored or submitted rules into the engine's Policy. Raises ValueError if they're invalid."""
    return Policy.from_dict({**rules, "version": version})


async def create_draft(
    session: AsyncSession, business: Business, owner_id: uuid.UUID, data: PolicyDraftIn
) -> BusinessPolicy:
    rules = data.rules.model_dump(mode="json")
    try:
        to_engine_policy(rules, version=1)  # validate with the engine's own rules
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))

    for _ in range(3):  # retry if two drafts are saved at the same moment
        latest = await session.scalar(
            select(func.max(BusinessPolicy.version)).where(BusinessPolicy.business_id == business.id)
        )
        version = (latest or 0) + 1
        draft = BusinessPolicy(business_id=business.id, version=version, raw_text=data.raw_text,
                               rules={**rules, "version": version})
        session.add(draft)
        audit.record(session, actor_type="owner", actor_id=owner_id, action="policy.draft_created",
                     business_id=business.id, details={"version": version})
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            continue
        await session.refresh(draft)
        return draft
    raise HTTPException(status.HTTP_409_CONFLICT, "Another change was saved at the same time. Try again.")


async def list_policies(session: AsyncSession, business: Business) -> list[BusinessPolicy]:
    result = await session.scalars(
        select(BusinessPolicy).where(BusinessPolicy.business_id == business.id).order_by(BusinessPolicy.version)
    )
    return list(result)


async def get_policy(session: AsyncSession, business: Business, version: int) -> BusinessPolicy:
    policy = await session.scalar(
        select(BusinessPolicy).where(BusinessPolicy.business_id == business.id, BusinessPolicy.version == version)
    )
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy version not found")
    return policy


async def confirm_policy(
    session: AsyncSession, business: Business, owner_id: uuid.UUID, version: int
) -> BusinessPolicy:
    policy = await get_policy(session, business, version)
    if policy.confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This version is already confirmed")
    if business.current_policy_version is not None and version <= business.current_policy_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "A newer version is already in use. Create a new draft instead.")

    policy.confirmed_at = get_clock().now()
    business.current_policy_version = version
    audit.record(session, actor_type="owner", actor_id=owner_id, action="policy.confirmed",
                 business_id=business.id, details={"version": version})
    await session.commit()
    await session.refresh(policy)
    return policy


def build_preview(policy: Policy, held: Decimal, holds_offered: list[Decimal]) -> PolicyPreviewOut:
    """Show the owner exactly what the rules engine will do in common situations. No AI involved."""
    start = datetime(2030, 1, 15, 10, 0, tzinfo=timezone.utc)  # any fixed moment works
    early = timedelta(hours=policy.free_cancel_hours + 24)
    late = timedelta(hours=max(policy.free_cancel_hours // 2, 1)) if policy.free_cancel_hours else timedelta(0)
    after_grace = start + timedelta(minutes=policy.grace_minutes + 1)

    scenarios = [
        ("Client attends", BookingFacts(start, held, Event.ATTENDED), after_grace),
        (f"Cancels {_hours(early)} before", BookingFacts(start, held, Event.CLIENT_CANCELLED, start - early), start),
    ]
    if policy.free_cancel_hours > 0:
        scenarios += [
            (f"Cancels {_hours(late)} before",
             BookingFacts(start, held, Event.CLIENT_CANCELLED, start - late), start),
            (f"Cancels {_hours(late)} before, slot refilled",
             BookingFacts(start, held, Event.CLIENT_CANCELLED, start - late, slot_refilled=True), start),
        ]
    scenarios += [
        (f"Client {policy.grace_minutes} min late", BookingFacts(start, held, Event.NO_SHOW),
         start + timedelta(minutes=policy.grace_minutes) - timedelta(seconds=1)),
        ("No-show", BookingFacts(start, held, Event.NO_SHOW), after_grace),
        ("Business cancels", BookingFacts(start, held, Event.OWNER_CANCELLED), start),
    ]

    rows = []
    for situation, facts, now in scenarios:
        decision = decide(facts, policy, now)
        if decision.action == Action.CAPTURE and decision.rule == "attended":
            outcome, charged = "Applied to the price", decision.amount
        elif decision.action == Action.CAPTURE:
            outcome, charged = f"Fee: {decision.amount}", decision.amount
        elif decision.action == Action.WAIT:
            outcome, charged = "Not a no-show yet", Decimal("0.00")
        else:
            outcome, charged = "No fee", Decimal("0.00")
        released = held - charged if decision.action in (Action.CAPTURE, Action.VOID) else Decimal("0.00")
        rows.append(PreviewRow(situation=situation, outcome=outcome, charged=charged, released=released,
                               needs_owner_approval=decision.needs_owner_approval, reason=decision.reason))

    return PolicyPreviewOut(version=policy.version, example_hold=held, rows=rows,
                            warnings=policy_warnings(policy, holds_offered))


def policy_warnings(policy: Policy, holds_offered: list[Decimal]) -> list[str]:
    warnings = []
    if policy.free_cancel_hours > BOOKING_WINDOW_HOURS:
        warnings.append(
            f"Bookings can only be made up to {BOOKING_WINDOW_HOURS} hours ahead, so with a "
            f"{policy.free_cancel_hours}-hour free cancellation window every booking would already be inside the fee window."
        )
    if holds_offered:
        smallest = min(holds_offered)
        for label, fee in (("late cancellation", policy.late_cancel_fee), ("no-show", policy.no_show_fee)):
            if fee.kind == FeeKind.FIXED and fee.value > smallest:
                warnings.append(
                    f"Your {label} fee is {fee.value:.2f}, but your smallest hold is {smallest:.2f}. "
                    f"For that service, the most you can collect is {smallest:.2f}."
                )
    return warnings


def holds_for(services: list[Service]) -> list[Decimal]:
    """The amounts that would be held for each active service and payment option."""
    holds = []
    for service in services:
        if not service.is_active:
            continue
        if "deposit_held" in service.payment_options:
            holds.append(service.deposit)
        if "full_held" in service.payment_options:
            holds.append(service.price)
    return [h for h in holds if h > 0]


def _hours(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    return f"{hours} hour" if hours == 1 else f"{hours} hours"