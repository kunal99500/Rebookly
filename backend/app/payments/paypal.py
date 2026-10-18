"""PayPal REST client. Every PayPal call in the app goes through this module.

Covers the MVP flow:
  create order (intent AUTHORIZE) -> buyer approves -> authorize -> capture (full or partial) or void

Design rules:
  * Pass a stable request_id for any call that might be retried (e.g. f"capture-{decision_id}").
    PayPal uses it as an idempotency key, so a retry can never capture twice.
  * Never store the payer's email or name from responses; keep IDs and card brand/last digits only.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx


def money(value: Decimal | str | int | float) -> str:
    """Format an amount the way PayPal expects: a string with two decimals."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class PayPalError(Exception):
    def __init__(self, status: int, name: str, message: str, debug_id: str | None, details: Any = None):
        super().__init__(f"PayPal {status} {name}: {message} (debug_id={debug_id})")
        self.status = status
        self.name = name
        self.message = message
        self.debug_id = debug_id
        self.details = details

    @classmethod
    def from_response(cls, response: httpx.Response) -> PayPalError:
        try:
            body = response.json()
        except ValueError:
            body = {}
        return cls(
            status=response.status_code,
            name=body.get("name") or body.get("error") or "UNKNOWN_ERROR",
            message=body.get("message") or body.get("error_description") or response.text[:300],
            debug_id=body.get("debug_id") or response.headers.get("paypal-debug-id"),
            details=body.get("details"),
        )


@dataclass(frozen=True)
class AuthorizationInfo:
    order_id: str
    authorization_id: str
    status: str
    amount: str
    currency: str
    expiration_time: str | None
    payment_method: str  # "paypal" or "card"
    card_brand: str | None = None
    card_last_digits: str | None = None


class PayPalClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str, timeout: float = 20.0):
        if not client_id or not client_secret:
            raise ValueError("PayPal client id and secret are required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._http.aclose()

    # ---------- auth ----------

    async def _get_token(self, force_refresh: bool = False) -> str:
        async with self._lock:
            if not force_refresh and self._token and time.monotonic() < self._token_expires_at:
                return self._token
            response = await self._http.post(
                "/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
            )
            if response.status_code != 200:
                raise PayPalError.from_response(response)
            body = response.json()
            self._token = body["access_token"]
            # Refresh a minute early to avoid using a token that expires mid-request.
            self._token_expires_at = time.monotonic() + int(body.get("expires_in", 300)) - 60
            return self._token

    async def _request(
        self, method: str, path: str, *, json: dict | None = None, request_id: str | None = None
    ) -> dict:
        headers = {"Content-Type": "application/json", "Prefer": "return=representation"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id

        for attempt in range(2):
            token = await self._get_token(force_refresh=attempt > 0)
            headers["Authorization"] = f"Bearer {token}"
            response = await self._http.request(method, path, json=json, headers=headers)
            if response.status_code == 401 and attempt == 0:
                continue  # token expired early; refresh once and retry with the same request id
            if response.status_code >= 400:
                raise PayPalError.from_response(response)
            return response.json() if response.content else {}
        raise PayPalError(401, "AUTHENTICATION_FAILURE", "Could not authenticate with PayPal", None)

    # ---------- orders ----------

    async def create_order(
        self,
        *,
        amount: Decimal | str,
        currency: str,
        reference_id: str,
        description: str | None = None,
        intent: str = "AUTHORIZE",
        payee_merchant_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        purchase_unit: dict[str, Any] = {
            "reference_id": reference_id,
            "custom_id": reference_id,
            "amount": {"currency_code": currency, "value": money(amount)},
        }
        if description:
            purchase_unit["description"] = description[:127]
        if payee_merchant_id:
            # Routes funds to a specific business account. Behaviour depends on account
            # permissions; test this in the sandbox spike before relying on it.
            purchase_unit["payee"] = {"merchant_id": payee_merchant_id}

        body = {"intent": intent, "purchase_units": [purchase_unit]}
        return await self._request(
            "POST", "/v2/checkout/orders", json=body,
            request_id=request_id or f"create-{reference_id}-{uuid.uuid4()}",
        )

    async def get_order(self, order_id: str) -> dict:
        return await self._request("GET", f"/v2/checkout/orders/{order_id}")

    async def authorize_order(self, order_id: str, request_id: str | None = None) -> AuthorizationInfo:
        order = await self._request(
            "POST",
            f"/v2/checkout/orders/{order_id}/authorize",
            json={},
            request_id=request_id or f"authorize-{order_id}",
        )
        return extract_authorization(order)

    # ---------- authorizations ----------

    async def get_authorization(self, authorization_id: str) -> dict:
        return await self._request("GET", f"/v2/payments/authorizations/{authorization_id}")

    async def capture_authorization(
        self,
        authorization_id: str,
        *,
        amount: Decimal | str | None = None,
        currency: str | None = None,
        final_capture: bool = True,
        request_id: str,
        note: str | None = None,
    ) -> dict:
        """Capture all (amount=None) or part of an authorization.

        request_id is required: captures move money, so retries must be idempotent.
        """
        body: dict[str, Any] = {"final_capture": final_capture}
        if amount is not None:
            if not currency:
                raise ValueError("currency is required for a partial capture")
            body["amount"] = {"currency_code": currency, "value": money(amount)}
        if note:
            body["note_to_payer"] = note[:255]
        return await self._request(
            "POST", f"/v2/payments/authorizations/{authorization_id}/capture",
            json=body, request_id=request_id,
        )

    async def void_authorization(self, authorization_id: str, *, request_id: str) -> dict:
        return await self._request(
            "POST", f"/v2/payments/authorizations/{authorization_id}/void", request_id=request_id
        )


def extract_authorization(order: dict) -> AuthorizationInfo:
    """Pull the fields we keep from an authorized order. Deliberately ignores payer email and name."""
    unit = order["purchase_units"][0]
    auth = unit["payments"]["authorizations"][0]
    source = order.get("payment_source", {})
    card = source.get("card")
    return AuthorizationInfo(
        order_id=order["id"],
        authorization_id=auth["id"],
        status=auth["status"],
        amount=auth["amount"]["value"],
        currency=auth["amount"]["currency_code"],
        expiration_time=auth.get("expiration_time"),
        payment_method="card" if card else "paypal",
        card_brand=card.get("brand") if card else None,
        card_last_digits=card.get("last_digits") if card else None,
    )