"""Tests for the PayPal client.

These run without internet: a fake PayPal (httpx.MockTransport) answers every request,
so we can check exactly what we send and how we handle each kind of reply.
"""
import json

import httpx
import pytest

from app.payments.paypal import PayPalClient, PayPalError, extract_authorization, money

BASE_URL = "https://api-m.sandbox.paypal.com"


# ---------- helpers ----------

def make_client(handler) -> PayPalClient:
    """A PayPalClient whose HTTP calls go to `handler` instead of the internet."""
    client = PayPalClient("test-id", "test-secret", BASE_URL)
    client._http = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return client


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "TEST-TOKEN", "expires_in": 3600})


def authorized_order(payment_source: dict) -> dict:
    """A trimmed example of what PayPal returns after authorizing an order."""
    return {
        "id": "ORDER1",
        "status": "COMPLETED",
        "payment_source": payment_source,
        "purchase_units": [{"payments": {"authorizations": [{
            "id": "AUTH1",
            "status": "CREATED",
            "amount": {"currency_code": "USD", "value": "20.00"},
            "expiration_time": "2026-11-15T00:00:00Z",
        }]}}],
    }


# ---------- money formatting ----------

@pytest.mark.parametrize("value, expected", [
    ("20", "20.00"),
    (20, "20.00"),
    ("7.775", "7.78"),
    ("0.1", "0.10"),
])
def test_money_always_has_two_decimals(value, expected):
    assert money(value) == expected


# ---------- reading PayPal responses ----------

def test_card_payment_keeps_brand_and_last_digits_only():
    order = authorized_order({"card": {"brand": "VISA", "last_digits": "4242", "name": "Test Buyer"}})
    info = extract_authorization(order)
    assert info.authorization_id == "AUTH1"
    assert info.payment_method == "card"
    assert info.card_brand == "VISA" and info.card_last_digits == "4242"
    assert "Test Buyer" not in str(info)


def test_paypal_payment_does_not_keep_payer_email():
    order = authorized_order({"paypal": {"email_address": "buyer@example.com", "name": {"given_name": "Ana"}}})
    info = extract_authorization(order)
    assert info.payment_method == "paypal"
    assert info.card_brand is None
    assert "buyer@example.com" not in str(info)
    assert "Ana" not in str(info)


# ---------- what we send to PayPal ----------

@pytest.mark.asyncio
async def test_create_order_uses_authorize_intent_and_booking_reference():
    seen = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            return token_response()
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "ORDER1", "status": "CREATED"})

    client = make_client(handler)
    await client.create_order(amount="20", currency="USD", reference_id="booking-42")
    unit = seen["body"]["purchase_units"][0]
    assert seen["body"]["intent"] == "AUTHORIZE"
    assert unit["reference_id"] == "booking-42" and unit["custom_id"] == "booking-42"
    assert unit["amount"] == {"currency_code": "USD", "value": "20.00"}
    await client.close()


@pytest.mark.asyncio
async def test_partial_capture_sends_amount_and_request_id():
    seen = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            return token_response()
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "CAP1", "status": "COMPLETED"})

    client = make_client(handler)
    result = await client.capture_authorization("AUTH1", amount="10", currency="USD", request_id="capture-dec-1")
    assert result["id"] == "CAP1"
    assert seen["path"] == "/v2/payments/authorizations/AUTH1/capture"
    assert seen["headers"]["PayPal-Request-Id"] == "capture-dec-1"
    assert seen["headers"]["Authorization"] == "Bearer TEST-TOKEN"
    assert seen["body"]["amount"] == {"currency_code": "USD", "value": "10.00"}
    assert seen["body"]["final_capture"] is True
    await client.close()


@pytest.mark.asyncio
async def test_full_capture_sends_no_amount():
    seen = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            return token_response()
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "CAP2", "status": "COMPLETED"})

    client = make_client(handler)
    await client.capture_authorization("AUTH1", request_id="capture-dec-2")
    assert "amount" not in seen["body"]
    await client.close()


@pytest.mark.asyncio
async def test_partial_capture_without_currency_is_refused():
    client = make_client(lambda request: token_response())
    with pytest.raises(ValueError, match="currency"):
        await client.capture_authorization("AUTH1", amount="10", request_id="capture-dec-3")
    await client.close()


# ---------- errors and token handling ----------

@pytest.mark.asyncio
async def test_paypal_error_keeps_debug_id():
    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            return token_response()
        return httpx.Response(422, json={
            "name": "UNPROCESSABLE_ENTITY", "message": "Authorization has been voided", "debug_id": "dbg123",
        })

    client = make_client(handler)
    with pytest.raises(PayPalError) as error:
        await client.void_authorization("AUTH1", request_id="void-1")
    assert error.value.status == 422
    assert error.value.debug_id == "dbg123"
    await client.close()


@pytest.mark.asyncio
async def test_wrong_credentials_raise_clear_error():
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": "invalid_client", "error_description": "Client Authentication failed"})

    client = make_client(handler)
    with pytest.raises(PayPalError) as error:
        await client.get_order("ORDER1")
    assert error.value.name == "invalid_client"
    await client.close()


@pytest.mark.asyncio
async def test_token_is_reused_between_requests():
    calls = {"token": 0}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            calls["token"] += 1
            return token_response()
        return httpx.Response(200, json={"id": "ORDER1", "status": "CREATED"})

    client = make_client(handler)
    await client.get_order("ORDER1")
    await client.get_order("ORDER1")
    assert calls["token"] == 1
    await client.close()


@pytest.mark.asyncio
async def test_expired_token_is_refreshed_once_with_same_request_id():
    calls = {"token": 0, "api": 0}
    request_ids = []

    def handler(request: httpx.Request):
        if request.url.path == "/v1/oauth2/token":
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": f"T{calls['token']}", "expires_in": 3600})
        calls["api"] += 1
        request_ids.append(request.headers.get("PayPal-Request-Id"))
        if calls["api"] == 1:
            return httpx.Response(401, json={"name": "AUTHENTICATION_FAILURE"})
        return httpx.Response(204)

    client = make_client(handler)
    await client.void_authorization("AUTH1", request_id="void-2")
    assert calls["token"] == 2
    assert request_ids == ["void-2", "void-2"]
    await client.close()


def test_missing_credentials_are_refused():
    with pytest.raises(ValueError):
        PayPalClient("", "", BASE_URL)