"""Finish money decisions that got stuck half-way (for example if the server restarted mid-capture)."""
from datetime import timedelta

from sqlalchemy import func, select

from app.db import session_scope
from app.models import Decision
from app.payments.paypal import PayPalClient
from app.services import outcomes

STUCK_AFTER = timedelta(minutes=5)


async def run(paypal: PayPalClient) -> int:
    async with session_scope() as session:
        ids = list(await session.scalars(
            select(Decision.id).where(
                Decision.status == "executing",
                Decision.updated_at < func.now() - STUCK_AFTER,  # database time, so the demo clock can't skew it
            ).limit(50)
        ))
    for decision_id in ids:
        async with session_scope() as session:
            await outcomes.recover(session, paypal, decision_id)
    return len(ids)