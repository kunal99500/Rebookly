"""Owner API: the dashboard. More panels (daily briefing, income protected) are added in later steps."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.db import get_session
from app.models import Business
from app.routers.owner.deps import get_owned_business
from app.schemas.dashboard import AttentionOut
from app.services import attention

router = APIRouter(prefix="/api/owner/businesses/{business_id}/dashboard", tags=["owner: dashboard"])


@router.get("/attention", response_model=AttentionOut)
async def needs_attention(business: Business = Depends(get_owned_business), session: AsyncSession = Depends(get_session)):
    """Possible no-shows, fees to approve, payments to retry, and holds that should be settled soon."""
    return await attention.needs_attention(session, business, get_clock().now())