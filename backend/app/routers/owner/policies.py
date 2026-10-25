"""Owner API: cancellation policies (drafts, preview, confirm)."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business, get_owner
from app.schemas.policy import PolicyDraftIn, PolicyOut, PolicyPreviewOut
from app.services import offerings, policies

router = APIRouter(prefix="/api/owner/businesses/{business_id}/policies", tags=["owner: policies"])


def _out(policy, business: Business) -> PolicyOut:
    result = PolicyOut.model_validate(policy)
    result.is_current = policy.version == business.current_policy_version
    return result


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
async def create_draft(
    data: PolicyDraftIn,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Save a new draft version. It isn't used for bookings until confirmed."""
    return _out(await policies.create_draft(session, business, owner.id, data), business)


@router.get("", response_model=list[PolicyOut])
async def list_versions(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    return [_out(p, business) for p in await policies.list_policies(session, business)]


@router.get("/{version}/preview", response_model=PolicyPreviewOut)
async def preview(
    version: int,
    held: Decimal | None = Query(default=None, gt=0, le=100000, description="Example hold; defaults to your first service's"),
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    """What the rules engine will do in common situations, plus warnings. Computed by code, not AI."""
    stored = await policies.get_policy(session, business, version)
    try:
        engine_policy = policies.to_engine_policy(stored.rules, stored.version)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))
    holds = policies.holds_for(await offerings.list_services(session, business, include_inactive=False))
    example = held or (holds[0] if holds else policies.DEFAULT_EXAMPLE_HOLD)
    return policies.build_preview(engine_policy, example.quantize(Decimal("0.01")), holds)


@router.post("/{version}/confirm", response_model=PolicyOut)
async def confirm(
    version: int,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Make this version the one new bookings use. Confirmed versions can never be edited."""
    return _out(await policies.confirm_policy(session, business, owner.id, version), business)