"""Public API (no sign-in): a live business's booking page data and its free slots."""
import uuid

from backend.app.auth.supabase_auth import AuthUser
from backend.app.routers.owner import businesses
from backend.app.routers.owner.deps import get_owned_business, get_owner
from backend.app.schemas.business import BusinessOut
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings

from app.clock import get_clock
from app.db import get_session
from app.media import photos
from app.models import Business, Service
from app.rules.policy_text import policy_summary
from app.schemas.public import (
    PublicBusinessOut, PublicPhotoOut, PublicPolicyOut, PublicRatingOut, PublicServiceOut, PublicSlotOut,
)
from app.services import offerings, policies, schedule

router = APIRouter(prefix="/api/public/businesses", tags=["public"])


async def get_live_business(slug: str, session: AsyncSession = Depends(get_session)) -> Business:
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


@router.get("/{slug}/services/{service_id}/slots", response_model=list[PublicSlotOut])
async def free_slots(
    service_id: uuid.UUID,
    business: Business = Depends(get_live_business),
    session: AsyncSession = Depends(get_session),
):
    """Times that can be booked right now: within the booking window, not full, and the provider is free."""
    service = await session.scalar(select(Service).where(
        Service.id == service_id, Service.business_id == business.id, Service.is_active.is_(True)
    ))
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    slots = await schedule.available_slots(session, business, service, get_clock().now())
    return [PublicSlotOut(id=s.id, starts_at=s.starts_at, ends_at=s.ends_at, seats_left=s.capacity - s.booked_count)
            for s in slots]


@router.post("/{business_id}/go-live", response_model=BusinessOut)
async def go_live(
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Open the business for bookings. Lists anything still missing if it isn't ready."""
    return await businesses.go_live(session, business, owner.id, get_settings().paypal_single_merchant)


@router.post("/{business_id}/pause", response_model=BusinessOut)
async def pause(
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Stop taking new bookings. Existing bookings stay as they are."""
    return await businesses.pause(session, business, owner.id)