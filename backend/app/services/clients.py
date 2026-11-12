"""Client profiles: named bookings, with phone numbers protected when provided."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_auth import AuthUser
from app.clock import get_clock
from app.models import Client
from app.schemas.client import ProfileIn
from app.security.phone import PhoneError, PhoneProtector
from app.services import audit


async def get_client(session: AsyncSession, user: AuthUser) -> Client | None:
    return await session.scalar(
        select(Client).where(Client.auth_user_id == user.id, Client.deleted_at.is_(None))
    )


async def require_client(session: AsyncSession, user: AuthUser) -> Client:
    if user.is_anonymous:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to access your account")
    client = await get_client(session, user)
    if client is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add your name and phone number first")
    return client


async def client_for_booking(
    session: AsyncSession, user: AuthUser, name: str, phones: PhoneProtector | None, allow_dev_phone: bool
) -> Client:
    """Return a client record, creating a phone-less guest record for anonymous bookings."""
    client = await get_client(session, user)
    if client is not None:
        client.name = name
        return client
    if user.is_anonymous:
        client = Client(id=uuid.uuid4(), auth_user_id=user.id, name=name)
        session.add(client)
        await session.flush()
        return client
    if phones is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Phone protection is not configured on the server")
    return await save_profile(session, user, ProfileIn(name=name), phones, allow_dev_phone=allow_dev_phone)


async def save_profile(
    session: AsyncSession, user: AuthUser, data: ProfileIn, phones: PhoneProtector, allow_dev_phone: bool
) -> Client:
    """Create or update the signed-in client's profile.

    The phone number comes from the Supabase sign-in (already verified by a one-time code).
    In development only, dev_phone can stand in for it so you can test with an email sign-in.
    """
    raw_phone = user.phone or (data.dev_phone if allow_dev_phone else None)
    if not raw_phone:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with your mobile number to book")
    try:
        protected = phones.protect(raw_phone)
    except PhoneError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))

    client = await get_client(session, user)
    other = await session.scalar(select(Client).where(Client.phone_hash == protected.hash))
    if other is not None and (client is None or other.id != client.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This number is already linked to another account")

    if client is None:
        client = Client(id=uuid.uuid4(), auth_user_id=user.id, name=data.name)
        session.add(client)
        action = "client.created"
    else:
        client.name = data.name
        action = "client.updated"
    client.phone_hash = protected.hash
    client.phone_encrypted = protected.encrypted
    client.phone_last4 = protected.last4
    client.phone_verified_at = get_clock().now()
    audit.record(session, actor_type="client", actor_id=user.id, action=action,
                 details={"client_id": str(client.id), "dev_phone": user.phone is None})
    await session.commit()
    await session.refresh(client)
    return client