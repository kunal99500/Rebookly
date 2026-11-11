"""Is a business's PayPal account ready to take Rebookly payments? Pure functions, no network.

PayPal tells us about a connected account through its "merchant integration" details.
We only treat an account as connected when it can actually receive money and has given Rebookly permission.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionCheck:
    status: str                  # "connected" or "needs_attention"
    problems: tuple[str, ...]    # what the owner needs to fix, in plain words


def tracking_id(business_id) -> str:
    """Our reference for one business's PayPal sign-up (PayPal returns it so we can find the account)."""
    return f"rebookly-{business_id}"


def check_integration(details: dict) -> ConnectionCheck:
    problems = []
    if not details.get("payments_receivable"):
        problems.append("Your PayPal account can't receive payments yet. Log in to PayPal to finish setting it up.")
    if not details.get("primary_email_confirmed"):
        problems.append("Confirm your email address with PayPal (check your inbox for PayPal's message).")
    if not details.get("oauth_integrations"):
        problems.append("Rebookly wasn't given permission to take payments for you. Please connect again.")
    return ConnectionCheck("needs_attention" if problems else "connected", tuple(problems))