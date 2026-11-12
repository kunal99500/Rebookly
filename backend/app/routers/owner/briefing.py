"""Owner API: today's briefing for the dashboard."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business
from app.services import briefing
from app.services.briefing import BriefingOut

router = APIRouter(prefix="/api/owner/businesses/{business_id}/briefing", tags=["owner: dashboard"])


@router.get("", response_model=BriefingOut)
async def todays_briefing(
    request: Request,
    refresh: bool = Query(default=False, description="Rebuild it now (a few times a day at most)"),
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    """Today at a glance: a short summary, the key facts, and suggestions. Saved for the day."""
    return await briefing.get_briefing(session, getattr(request.app.state, "ai", None), business, refresh)