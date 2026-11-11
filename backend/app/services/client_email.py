"""A client's optional email: added with a 6-digit code, so we never email an address the client doesn't control."""
import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.models import Client
from app.notifications.outbox import enqueue

CODE_TTL = timedelta(minutes=15)
RESEND_GAP = timedelta(seconds=60)
MAX_ATTEMPTS = 5
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")


def normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address")
    return email


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def code_hash(secret: str, client_id, code: str) -> str:
    """Codes are stored only as a keyed hash, tied to the client, so a database leak doesn't reveal them."""
    return hmac.new(secret.encode(), f"{client_id}:{code}".encode(), hashlib.sha256).hexdigest()


def code_matches(secret: str, client_id, code: str, stored: str | None) -> bool:
    return bool(stored) and hmac.compare_digest(code_hash(secret, client_id, code.strip()), stored)


async def start(session: AsyncSession, client: Client, email: str, secret: str) -> None:
    now = get_clock().now()
    if client.email_code_expires_at and now < client.email_code_expires_at - CODE_TTL + RESEND_GAP:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Please wait a minute before asking for another code")
    code = new_code()
    client.email_pending = email
    client.email_code_hash = code_hash(secret, client.id, code)
    client.email_code_expires_at = now + CODE_TTL
    client.email_code_attempts = 0
    await enqueue(session, kind="email_code", to_address=email, recipient_type="client", payload={"code": code},
                  dedupe_key=f"email_code:{client.id}:{now.isoformat()}")
    await session.commit()


async def verify(session: AsyncSession, client: Client, code: str, secret: str) -> Client:
    now = get_clock().now()
    if not client.email_pending or not client.email_code_expires_at or now > client.email_code_expires_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "That code has expired. Ask for a new one.")
    if client.email_code_attempts >= MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Too many tries. Ask for a new code.")
    client.email_code_attempts += 1
    if not code_matches(secret, client.id, code, client.email_code_hash):
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That code isn't right. Check it and try again.")
    client.email, client.email_verified_at = client.email_pending, now
    client.email_pending = client.email_code_hash = client.email_code_expires_at = None
    await session.commit()
    await session.refresh(client)
    return client


async def remove(session: AsyncSession, client: Client) -> None:
    client.email = client.email_verified_at = client.email_pending = None
    client.email_code_hash = client.email_code_expires_at = None
    await session.commit()