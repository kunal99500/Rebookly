"""One-time setup: create the "Rebookly Pro" product and monthly plan in PayPal, then print the plan ID.

    python -m scripts.create_pro_plan 499 INR

Put the printed ID in .env as PAYPAL_PRO_PLAN_ID. Run it again for the live environment when you launch.
"""
import asyncio
import sys

from app.config import get_settings
from app.payments.subscriptions import PayPalSubscriptions


async def main(price: str, currency: str) -> None:
    s = get_settings()
    client = PayPalSubscriptions(s.paypal_client_id, s.paypal_client_secret.get_secret_value(), s.paypal_env)
    try:
        product = await client._call("POST", "/v1/catalogs/products",
                                     {"name": "Rebookly Pro", "type": "SERVICE", "category": "SOFTWARE"})
        plan = await client._call("POST", "/v1/billing/plans", {
            "product_id": product["id"],
            "name": "Rebookly Pro (monthly)",
            "description": "No per-visit fee on bookings",
            "billing_cycles": [{
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0,
                "pricing_scheme": {"fixed_price": {"value": price, "currency_code": currency}},
            }],
            "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 3},
        })
        print("PAYPAL_PRO_PLAN_ID=" + plan["id"])
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "499", sys.argv[2] if len(sys.argv) > 2 else "INR"))
