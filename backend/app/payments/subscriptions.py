"""PayPal subscriptions for the Pro plan (the owner pays Rebookly monthly).

A small, separate client so the booking-payments code stays untouched. It uses Rebookly's own PayPal
app credentials (the same PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET).

One-time setup (run once per environment): create a product and a monthly plan in PayPal, then put the
plan's ID in PAYPAL_PRO_PLAN_ID. See scripts/create_pro_plan.py.
"""
import time
from datetime import datetime

import httpx

BASE = {"sandbox": "https://api-m.sandbox.paypal.com", "live": "https://api-m.paypal.com"}


class SubscriptionError(Exception):
    pass


class PayPalSubscriptions:
    def __init__(self, client_id: str, client_secret: str, env: str = "sandbox", timeout: float = 20):
        self._id, self._secret = client_id, client_secret
        self._base = BASE["live" if env == "live" else "sandbox"]
        self._http = httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._token_until = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _auth(self) -> dict[str, str]:
        if not self._token or time.monotonic() > self._token_until:
            response = await self._http.post(f"{self._base}/v1/oauth2/token", auth=(self._id, self._secret),
                                             data={"grant_type": "client_credentials"})
            if response.status_code != 200:
                raise SubscriptionError("Couldn't sign in to PayPal")
            body = response.json()
            self._token = body["access_token"]
            self._token_until = time.monotonic() + int(body.get("expires_in", 3000)) - 60
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _call(self, method: str, path: str, json: dict | None = None, request_id: str | None = None) -> dict:
        headers = await self._auth()
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        response = await self._http.request(method, f"{self._base}{path}", headers=headers, json=json)
        if response.status_code >= 400:
            raise SubscriptionError(f"PayPal answered {response.status_code}")
        return response.json() if response.content else {}

    async def start(self, *, plan_id: str, business_id: str, return_url: str, cancel_url: str) -> tuple[str, str]:
        """Create a subscription waiting for the owner's approval. Returns (subscription id, approval link)."""
        body = await self._call("POST", "/v1/billing/subscriptions", {
            "plan_id": plan_id,
            "custom_id": business_id,
            "application_context": {
                "brand_name": "Rebookly", "user_action": "SUBSCRIBE_NOW", "shipping_preference": "NO_SHIPPING",
                "return_url": return_url, "cancel_url": cancel_url,
            },
        }, request_id=f"pro-{business_id}-{int(time.time() // 600)}")
        link = next((l["href"] for l in body.get("links", []) if l.get("rel") == "approve"), None)
        if not body.get("id") or not link:
            raise SubscriptionError("PayPal didn't return an approval link")
        return body["id"], link

    async def status(self, subscription_id: str) -> tuple[str, datetime | None]:
        """(PayPal status, next billing time) for a subscription."""
        body = await self._call("GET", f"/v1/billing/subscriptions/{subscription_id}")
        next_time = (body.get("billing_info") or {}).get("next_billing_time")
        return body.get("status", ""), datetime.fromisoformat(next_time.replace("Z", "+00:00")) if next_time else None

    async def cancel(self, subscription_id: str, reason: str = "Cancelled by the business owner") -> None:
        await self._call("POST", f"/v1/billing/subscriptions/{subscription_id}/cancel", {"reason": reason})
