"""Signed links. A checkout link carries a signature so only the person who started the booking can open it.

The signature is an HMAC of the booking ID with a server secret, so it can't be guessed or altered,
and nothing needs to be stored.
"""
import hashlib
import hmac
import uuid


def _sign(secret: str, purpose: str, value: str) -> str:
    message = f"{purpose}:{value}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:40]


def checkout_signature(secret: str, booking_id: uuid.UUID) -> str:
    return _sign(secret, "checkout-link", str(booking_id))


def verify_checkout_signature(secret: str, booking_id: uuid.UUID, signature: str) -> bool:
    return hmac.compare_digest(checkout_signature(secret, booking_id), signature or "")