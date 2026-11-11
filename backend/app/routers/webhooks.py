"""PayPal calls this when something happens to a payment. No sign-in: every event's signature is checked
with PayPal before we act on it, and we then ask PayPal for the current state rather than trusting the body."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.payments import webhooks
from app.payments.paypal import PayPalError

logger = logging.getLogger("rebookly.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"], include_in_schema=False)

SIGNATURE_HEADERS = ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id",
                     "paypal-transmission-sig", "paypal-transmission-time")


@router.post("/paypal")
async def paypal_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    paypal = getattr(request.app.state, "paypal", None)
    webhook_id = get_settings().paypal_webhook_id
    if paypal is None or not webhook_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "PayPal webhooks aren't configured")

    raw = await request.body()
    if len(raw) > 200_000:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Too large")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON")

    headers = {name: request.headers.get(name, "") for name in SIGNATURE_HEADERS}
    try:
        genuine = await paypal.verify_webhook_signature(headers=headers, event=event, webhook_id=webhook_id)
    except PayPalError:
        # We can't check it right now: answer with an error so PayPal delivers it again later.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Can't verify right now")
    if not genuine:
        logger.warning("Rejected a PayPal webhook with an invalid signature")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature")

    row = await webhooks.record(session, event)
    if row is None:
        return {"status": "duplicate"}
    # Once recorded, always answer 200: our own retry job handles anything that fails from here.
    return {"status": await webhooks.process(session, paypal, row)}