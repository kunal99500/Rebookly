"""Public API (no sign-in): a live business's booking page, its free times, and class sessions."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.compliance import profiles as tax_profiles
from app.db import get_session
from app.media import photos
from app.models import Business, Service
from app.rules.policy_text import policy_summary
from app.schemas.availability import AvailabilityOut, AvailabilityRequest, StaffChoice, TimeChoice
from app.schemas.public import (
    PublicBusinessOut, PublicPhotoOut, PublicPolicyOut, PublicRatingOut, PublicServiceOut, PublicSlotOut,
)
from app.services import availability, offerings, policies, schedule

router = APIRouter(prefix="/api/public/businesses", tags=["public"])


# ---------- shared helpers ----------

async def get_live_business(slug: str, session: AsyncSession = Depends(get_session)) -> Business:
    """Only live businesses are visible to the public. Drafts and paused businesses return "not found"."""
    business = await session.scalar(select(Business).where(Business.slug == slug, Business.status == "live"))
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business


def _photo(storage, photo) -> PublicPhotoOut:
    return PublicPhotoOut(
        url=storage.public_url(photos.PHOTO_BUCKET, photo.storage_path),
        thumb_url=storage.public_url(photos.PHOTO_BUCKET, photo.thumb_path),
        width=photo.width, height=photo.height, alt_text=photo.alt_text,
    )


# ---------- the booking page ----------

@router.get("/{slug}", response_model=PublicBusinessOut)
async def business_page(
    request: Request, business: Business = Depends(get_live_business), session: AsyncSession = Depends(get_session)
):
    """Everything the booking page needs: photos, services, prices, rating, and the policy in plain words."""
    stored = await policies.get_policy(session, business, business.current_policy_version)
    engine_policy = policies.to_engine_policy(stored.rules, stored.version)
    services = await offerings.list_services(session, business, include_inactive=False)

    storage = getattr(request.app.state, "storage", None)
    all_photos = await photos.list_photos(session, business.id, public_only=True) if storage else []
    cover = next((p for p in all_photos if p.kind == "cover"), None)
    gallery = [p for p in all_photos if p.kind == "gallery"]
    service_photos = {p.service_id: p for p in all_photos if p.kind == "service"}

    return PublicBusinessOut(
        name=business.name, slug=business.slug, description=business.description, category=business.category,
        vocabulary=business.vocabulary, timezone=business.timezone, currency=business.currency,
        address=business.address,
        cover=_photo(storage, cover) if cover else None,
        gallery=[_photo(storage, p) for p in gallery],
        rating=PublicRatingOut(average=business.rating_average, count=business.rating_count),
        services=[
            PublicServiceOut(
                id=s.id, name=s.name, description=s.description, duration_minutes=s.duration_minutes,
                price=s.price, deposit=s.deposit, payment_options=s.payment_options,
                photo=_photo(storage, service_photos[s.id]) if s.id in service_photos else None,
            )
            for s in services
        ],
        policy=PublicPolicyOut(
            version=engine_policy.version, summary=policy_summary(engine_policy),
            free_cancel_hours=engine_policy.free_cancel_hours, grace_minutes=engine_policy.grace_minutes,
        ),
    )


# ---------- appointments: times calculated from the services chosen ----------

@router.post("/{slug}/availability", response_model=AvailabilityOut)
async def available_times(
    data: AvailabilityRequest,
    business: Business = Depends(get_live_business),
    session: AsyncSession = Depends(get_session),
):
    """Start times where the whole visit fits, with who is free at each time.

    Send the services the client picked (e.g. haircut + wash). Price, tax, deposit and length are worked out here,
    so the client sees the real total before booking.
    """
    plan, staff, options = await availability.available_times(
        session, business, data.service_ids, data.staff_id, get_clock().now())
    taxes, tax_profile = await tax_profiles.visit_tax(session, business.id, [line.price for line in plan.lines])
    charges_tax = bool(tax_profile and tax_profile.tax_registered)
    names = {s.id: s.name for s in staff}
    return AvailabilityOut(
        duration_minutes=plan.duration_minutes,
        price=plan.price,
        deposit=plan.deposit,
        tax_label=tax_profile.tax_label if charges_tax else None,
        tax_amount=taxes.tax_total,
        prices_include_tax=tax_profile.prices_include_tax if charges_tax else True,
        total_price=taxes.gross_total,
        currency=business.currency,
        payment_options=list(plan.payment_options),
        staff_choices=[StaffChoice(id=s.id, name=s.name) for s in staff],
        times=[TimeChoice(starts_at=o.starts_at, ends_at=o.ends_at,
                          staff=[StaffChoice(id=i, name=names[i]) for i in o.staff_ids]) for o in options],
    )


# ---------- classes: fixed sessions with seats ----------

@router.get("/{slug}/services/{service_id}/slots", response_model=list[PublicSlotOut])
async def free_slots(
    service_id: uuid.UUID,
    business: Business = Depends(get_live_business),
    session: AsyncSession = Depends(get_session),
):
    """Class sessions that can be booked right now: within the booking window, not full, and not blocked.

    Appointment services don't use pre-made slots; use the availability endpoint for those.
    """
    service = await session.scalar(select(Service).where(
        Service.id == service_id, Service.business_id == business.id, Service.is_active.is_(True)
    ))
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    if service.booking_mode != "class":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This service is booked by appointment. Use the availability endpoint instead.")
    slots = await schedule.available_slots(session, business, service, get_clock().now())
    return [PublicSlotOut(id=s.id, starts_at=s.starts_at, ends_at=s.ends_at, seats_left=s.capacity - s.booked_count)
            for s in slots]