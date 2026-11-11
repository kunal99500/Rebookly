"""Owner API: set up a business from a plain-words description.

1. POST /interview - the assistant asks a few friendly questions about anything important that's missing
                     (repeat with the answers until status is "ready", at most 3 rounds, or skip anytime).
2. POST /draft     - the AI drafts business details, services, hours and policy. Nothing is saved.
3. The owner reviews and edits the draft in the app.
4. POST /apply     - saves the (edited) draft through the normal setup logic. The policy is saved as a
                     draft version: the owner still previews and confirms it before it applies to bookings.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import onboarding
from app.ai.client import AIOutputError, AIUnavailable
from app.ai.onboarding import (
    InterviewOut, InterviewRequest, OnboardingDraft, OnboardingDraftOut, OnboardingRequest,
)
from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.routers.owner.deps import get_owner
from app.services import businesses, offerings, policies, schedule

router = APIRouter(prefix="/api/owner/onboarding", tags=["owner: AI onboarding"])

NEXT_STEPS = [
    "Preview and confirm your cancellation policy",
    "Set your location (country, state, city and map position)",
    "Add your tax details, if you're registered",
    "Add photos of your business",
    "Connect PayPal and go live",
]


class OnboardingApplied(BaseModel):
    business_id: uuid.UUID
    slug: str
    services_created: int
    hours_set: bool
    policy_version: int          # a draft: preview and confirm it next
    next_steps: list[str]


def _ai(request: Request):
    ai = getattr(request.app.state, "ai", None)
    if ai is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The setup assistant isn't available right now. You can set up step by step instead.")
    return ai


@router.post("/interview", response_model=InterviewOut)
async def interview(data: InterviewRequest, request: Request, owner: AuthUser = Depends(get_owner)):
    """Tell us about your business; the assistant asks a few quick questions about anything important it needs.

    Send the description (and any answers so far). When status is "ready", call /draft with the same content.
    """
    ai = _ai(request)
    base = OnboardingRequest(**data.model_dump(exclude={"round"}))
    try:
        return await onboarding.interview(ai, base, data.round)
    except (AIUnavailable, AIOutputError):
        # Questions are a nice-to-have: if the assistant can't ask them, go straight to the draft.
        return InterviewOut(status="ready", summary="Let's prepare your setup with what you've told us.",
                            round=data.round, max_rounds=onboarding.MAX_INTERVIEW_ROUNDS)


@router.post("/draft", response_model=OnboardingDraftOut)
async def draft_setup(data: OnboardingRequest, request: Request, owner: AuthUser = Depends(get_owner)):
    """Get a complete draft setup from your description and answers. Nothing is saved."""
    ai = _ai(request)
    try:
        return await onboarding.draft_setup(ai, data, owner.id)
    except AIUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The setup assistant isn't responding. Please try again, or set up step by step.")
    except AIOutputError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "The assistant couldn't build a complete draft. Try adding a bit more detail.")


@router.post("/apply", response_model=OnboardingApplied, status_code=status.HTTP_201_CREATED)
async def apply_setup(
    data: OnboardingDraft,
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Save the reviewed draft: business, services, opening hours, and a draft cancellation policy."""
    business = await businesses.create_business(session, owner.id, data.business)
    for service in data.services:
        await offerings.create_service(session, business, owner.id, service)
    if data.hours is not None:
        await schedule.replace_hours(session, business, owner.id, data.hours)
    policy = await policies.create_draft(session, business, owner.id, data.policy)
    return OnboardingApplied(
        business_id=business.id, slug=business.slug, services_created=len(data.services),
        hours_set=data.hours is not None, policy_version=policy.version, next_steps=NEXT_STEPS,
    )