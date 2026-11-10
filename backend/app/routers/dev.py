"""Development-only routes: PayPal sandbox test page and simulated clock control.

Mounted only when ENABLE_DEV_ROUTES=true, which config.py forbids in production and live mode.
"""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.clock import SimulatedClock, get_clock
from app.config import get_settings
from app.payments.paypal import PayPalClient, PayPalError

router = APIRouter(tags=["dev"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


# ---------- helpers ----------

def _paypal(request: Request) -> PayPalClient:
    client = getattr(request.app.state, "paypal", None)
    if client is None:
        raise HTTPException(503, "PayPal is not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")
    return client


def _paypal_http_error(err: PayPalError) -> HTTPException:
    """Turn a PayPal failure into a clear API error that keeps PayPal's debug ID."""
    return HTTPException(
        status_code=502,
        detail={"paypal_error": err.name, "message": err.message, "debug_id": err.debug_id, "details": err.details},
    )


# ---------- sandbox test page ----------

@router.get("/dev/checkout", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    amount: Decimal = Query(Decimal("20.00"), gt=0, le=10000),
    payee: str | None = Query(None, max_length=50),
):
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "dev/checkout.html",
        {
            "client_id": settings.paypal_client_id,  # the client ID is public; the secret never goes here
            "currency": settings.default_currency,
            "amount": f"{amount:.2f}",
            "payee": payee,
        },
    )


# ---------- payment endpoints used by the test page ----------

class CreateOrderIn(BaseModel):
    amount: Decimal = Field(gt=0, le=10000)
    reference: str = Field(min_length=1, max_length=100)
    payee_merchant_id: str | None = Field(default=None, max_length=50)


class CaptureIn(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, le=10000)
    final_capture: bool = True


@router.post("/api/dev/orders")
async def create_order(body: CreateOrderIn, request: Request):
    settings = get_settings()
    try:
        order = await _paypal(request).create_order(
            amount=body.amount,
            currency=settings.default_currency,
            reference_id=body.reference,
            description="Rebookly deposit hold (sandbox test)",
            payee_merchant_id=body.payee_merchant_id,
        )
    except PayPalError as err:
        raise _paypal_http_error(err)
    return {"id": order["id"], "status": order["status"]}


@router.post("/api/dev/orders/{order_id}/authorize")
async def authorize_order(order_id: str, request: Request):
    try:
        info = await _paypal(request).authorize_order(order_id)
    except PayPalError as err:
        raise _paypal_http_error(err)
    return info.__dict__


@router.post("/api/dev/authorizations/{authorization_id}/capture")
async def capture(authorization_id: str, body: CaptureIn, request: Request):
    settings = get_settings()
    try:
        result = await _paypal(request).capture_authorization(
            authorization_id,
            amount=body.amount,
            currency=settings.default_currency if body.amount is not None else None,
            final_capture=body.final_capture,
            request_id=f"dev-capture-{authorization_id}-{uuid4()}",
        )
    except PayPalError as err:
        raise _paypal_http_error(err)
    return {"capture_id": result.get("id"), "status": result.get("status"), "amount": result.get("amount")}


@router.post("/api/dev/authorizations/{authorization_id}/void")
async def void(authorization_id: str, request: Request):
    paypal = _paypal(request)
    try:
        await paypal.void_authorization(authorization_id, request_id=f"dev-void-{authorization_id}")
        details = await paypal.get_authorization(authorization_id)
    except PayPalError as err:
        raise _paypal_http_error(err)
    return {"authorization_id": authorization_id, "status": details.get("status")}


@router.get("/api/dev/authorizations/{authorization_id}")
async def get_authorization(authorization_id: str, request: Request):
    try:
        details = await _paypal(request).get_authorization(authorization_id)
    except PayPalError as err:
        raise _paypal_http_error(err)
    return {
        "id": details.get("id"),
        "status": details.get("status"),
        "amount": details.get("amount"),
        "expiration_time": details.get("expiration_time"),
    }


# ---------- simulated clock ----------

def _sim_clock() -> SimulatedClock:
    clock = get_clock()
    if not isinstance(clock, SimulatedClock):
        raise HTTPException(400, "Simulated clock is off. Set SIMULATED_CLOCK=true in .env.")
    return clock


@router.get("/api/dev/clock")
async def clock_now():
    clock = get_clock()
    offset = clock.offset if isinstance(clock, SimulatedClock) else timedelta(0)
    return {"now": clock.now().isoformat(), "offset_minutes": int(offset.total_seconds() // 60)}


@router.post("/api/dev/clock/advance")
async def clock_advance(minutes: int = Query(ge=-43200, le=43200)):
    try:
        now = _sim_clock().advance(timedelta(minutes=minutes))
    except ValueError as err:
        raise HTTPException(400, str(err))
    return {"now": now.isoformat()}


@router.post("/api/dev/clock/reset")
async def clock_reset():
    return {"now": _sim_clock().reset().isoformat()}


# ---------- background jobs ----------

@router.post("/api/dev/jobs/run")
async def run_jobs(request: Request):
    """Run every background job once, right now (instead of waiting for the timer)."""
    runner = getattr(request.app.state, "jobs", None)
    if runner is None:
        raise HTTPException(503, "Background jobs are off. Set ENABLE_JOBS=true and restart.")
    return await runner.run_all()