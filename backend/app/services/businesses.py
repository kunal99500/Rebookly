"""Business logic for creating and managing businesses."""
import re
import unicodedata
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AvailabilityRule, Business, Service
from app.schemas.business import BusinessCreate, BusinessUpdate
from app.services import audit
from app.services import audit, team

MAX_SLUG_LENGTH = 60


def slugify(name: str) -> str:
    """'Lumen Fitness & Yoga!' -> 'lumen-fitness-yoga'."""
    ascii_text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = slug[:MAX_SLUG_LENGTH].strip("-")
    return slug or "business"


async def _slug_taken(session: AsyncSession, slug: str) -> bool:
    return (await session.scalar(select(Business.id).where(Business.slug == slug))) is not None


async def unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate, number = base, 2
    while await _slug_taken(session, candidate):
        suffix = f"-{number}"
        candidate = base[: MAX_SLUG_LENGTH - len(suffix)].rstrip("-") + suffix
        number += 1
    return candidate


async def create_business(session: AsyncSession, owner_id: uuid.UUID, data: BusinessCreate) -> Business:
    for _ in range(3):  # retry if two owners grab the same slug at the same moment
        business = Business(
            id=uuid.uuid4(),  # set now so the audit entry can reference it
            owner_user_id=owner_id,
            slug=await unique_slug(session, data.name),
            **data.model_dump(),
        )
        session.add(business)
        audit.record(session, actor_type="owner", actor_id=owner_id, action="business.created",
                     business_id=business.id, details={"name": business.name, "category": business.category})
        await team.ensure_defaults(session, business)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            continue
        await session.refresh(business)
        return business
    raise RuntimeError("Could not create a unique booking link. Try a slightly different name.")


async def list_owner_businesses(session: AsyncSession, owner_id: uuid.UUID) -> list[Business]:
    result = await session.scalars(
        select(Business).where(Business.owner_user_id == owner_id).order_by(Business.created_at)
    )
    return list(result)


async def update_business(
    session: AsyncSession, business: Business, owner_id: uuid.UUID, data: BusinessUpdate
) -> Business:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(business, field, value)
    if changes:
        audit.record(session, actor_type="owner", actor_id=owner_id, action="business.updated",
                     business_id=business.id, details={"fields": sorted(changes)})
        await session.commit()
        await session.refresh(business)
    return business


async def readiness_problems(session: AsyncSession, business: Business, single_merchant: bool) -> list[str]:
    """Everything still missing before clients can book. Empty list = ready."""
    problems = []
    if business.current_policy_version is None:
        problems.append("Confirm a cancellation policy")
    services = await session.scalar(
        select(func.count()).select_from(Service).where(Service.business_id == business.id, Service.is_active.is_(True))
    )
    if not services:
        problems.append("Add at least one active service")
    hours = await session.scalar(
        select(func.count()).select_from(AvailabilityRule).where(AvailabilityRule.business_id == business.id)
    )
    if not hours:
        problems.append("Set your opening hours")
    if not single_merchant and business.paypal_status != "connected":
        problems.append("Connect your PayPal account")
    return problems


async def go_live(session: AsyncSession, business: Business, owner_id: uuid.UUID, single_merchant: bool) -> Business:
    problems = await readiness_problems(session, business, single_merchant)
    if problems:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "Not ready to take bookings yet", "missing": problems})
    business.status = "live"
    if single_merchant:
        business.paypal_status = "connected"  # sandbox: payments go to the platform's own PayPal account
    audit.record(session, actor_type="owner", actor_id=owner_id, action="business.went_live", business_id=business.id)
    await session.commit()
    await session.refresh(business)
    return business


async def pause(session: AsyncSession, business: Business, owner_id: uuid.UUID) -> Business:
    """Stop new bookings. Existing bookings are not affected."""
    if business.status == "live":
        business.status = "paused"
        audit.record(session, actor_type="owner", actor_id=owner_id, action="business.paused", business_id=business.id)
        await session.commit()
        await session.refresh(business)
    return business