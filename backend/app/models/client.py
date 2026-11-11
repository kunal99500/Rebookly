"""A person who books appointments. Only a name and a verified mobile number are collected."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String,Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey


class Client(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "clients"

    # The client's Supabase login (created when they verify their phone with a one-time code).
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    name: Mapped[str] = mapped_column(String(80))

    # The phone number is never stored as plain text:
    #   phone_hash      - a keyed hash, used only to look a client up by number
    #   phone_encrypted - the encrypted number, decrypted only to show it to the business they booked
    #   phone_last4     - for masked display, like +44 •••• ••3456
    phone_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    phone_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    phone_last4: Mapped[str | None] = mapped_column(String(4))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set when the client asks to delete their data; personal fields are then wiped.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        # Optional email for confirmations and reminders. Only used once verified with a code.
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_pending: Mapped[str | None] = mapped_column(String(320))          # waiting for its code
    email_code_hash: Mapped[str | None] = mapped_column(String(64))
    email_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")