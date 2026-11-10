"""Owner API: the approvals inbox. Approve, lower, or waive fees, and retry anything PayPal couldn't finish."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.db import get_session
from app.models import Booking, Business, Decision
from app.routers.owner.deps import get_owned_business, get_owner, get_paypal
from app.schemas.outcome import ApproveIn, DecisionOut, WaiveIn
from app.services import outcomes

router = APIRouter(prefix="/api/owner/businesses/{business_id}/decisions", tags=["owner: approvals"])

DecisionStatus = Literal["pending_approval", "approved", "waived", "executing", "executed", "failed", "superseded"]


async def _business_decision(session: AsyncSession, business: Business, decision_id: uuid.UUID) -> Decision:
    decision = await session.scalar(
        select(Decision).join(Booking, Booking.id == Decision.booking_id)
        .where(Decision.id == decision_id, Booking.business_id == business.id))
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision not found")
    return decision


@router.get("", response_model=list[DecisionOut])
async def list_decisions(
    status_filter: DecisionStatus = Query(default="pending_approval", alias="status"),
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    """Your approvals inbox (pending by default). Use status=failed to see anything PayPal couldn't complete."""
    rows = await session.scalars(
        select(Decision).join(Booking, Booking.id == Decision.booking_id)
        .where(Booking.business_id == business.id, Decision.status == status_filter)
        .order_by(Decision.created_at)
    )
    return list(rows)


@router.post("/{decision_id}/approve", response_model=DecisionOut)
async def approve(
    decision_id: uuid.UUID, data: ApproveIn, request: Request,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Charge the fee (or a lower amount). The rest of the hold is released."""
    decision = await _business_decision(session, business, decision_id)
    return await outcomes.approve(session, get_paypal(request), decision.id, owner.id, data.final_amount, data.note)


@router.post("/{decision_id}/waive", response_model=DecisionOut)
async def waive(
    decision_id: uuid.UUID, data: WaiveIn, request: Request,
    business: Business = Depends(get_owned_business),
    owner: AuthUser = Depends(get_owner),
    session: AsyncSession = Depends(get_session),
):
    """Don't charge anything. The whole hold is released."""
    decision = await _business_decision(session, business, decision_id)
    return await outcomes.waive(session, get_paypal(request), decision.id, owner.id, data.note)


@router.post("/{decision_id}/retry", response_model=DecisionOut)
async def retry(
    decision_id: uuid.UUID, request: Request,
    business: Business = Depends(get_owned_business),
    session: AsyncSession = Depends(get_session),
):
    """Try a failed payment action again. PayPal is checked first, so nothing is ever charged twice."""
    decision = await _business_decision(session, business, decision_id)
    if decision.status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed actions can be retried")
    return await outcomes.recover(session, get_paypal(request), decision.id)