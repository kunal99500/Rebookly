"""Protects client phone numbers.

A phone number is never stored as plain text. We keep three things:
  hash       - HMAC-SHA256 of the number with a secret key: lets us find a client by number
  encrypted  - the number encrypted with a secret key: decrypted only to show it to the business they booked
  last4      - the last four digits, for masked display like +44 •••• ••3456
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import phonenumbers
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

MIN_HASH_KEY_LENGTH = 32


class PhoneError(ValueError):
    """The number isn't a valid phone number. The message is safe to show to the user."""


def normalize_phone(raw: str, default_region: str | None = None) -> str:
    """Turn any reasonable input into international format, e.g. '+447911123456'."""
    text = (raw or "").strip()
    if text and text[0].isdigit() and default_region is None:
        text = "+" + text  # Supabase tokens store numbers without the leading +
    try:
        number = phonenumbers.parse(text, default_region)
    except phonenumbers.NumberParseException:
        raise PhoneError("Enter a valid mobile number, including the country code")
    if not phonenumbers.is_valid_number(number):
        raise PhoneError("Enter a valid mobile number, including the country code")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def mask_phone(e164: str) -> str:
    """'+447911123456' -> '+44 •••• ••3456'."""
    number = phonenumbers.parse(e164, None)
    return f"+{number.country_code} •••• ••{e164[-4:]}"


@dataclass(frozen=True)
class ProtectedPhone:
    hash: str
    encrypted: bytes
    last4: str


class PhoneProtector:
    def __init__(self, encryption_keys: str, hash_key: str):
        keys = [key.strip() for key in (encryption_keys or "").split(",") if key.strip()]
        if not keys:
            raise ValueError("DATA_ENCRYPTION_KEY is not set")
        try:
            self._fernet = MultiFernet([Fernet(key) for key in keys])
        except ValueError:
            raise ValueError("DATA_ENCRYPTION_KEY is not a valid key. Generate one as described in the README.")
        if len(hash_key or "") < MIN_HASH_KEY_LENGTH:
            raise ValueError(f"PHONE_HASH_KEY must be at least {MIN_HASH_KEY_LENGTH} characters")
        self._hash_key = hash_key.encode()

    def hash(self, e164: str) -> str:
        return hmac.new(self._hash_key, e164.encode(), hashlib.sha256).hexdigest()

    def protect(self, raw: str, default_region: str | None = None) -> ProtectedPhone:
        e164 = normalize_phone(raw, default_region)
        return ProtectedPhone(
            hash=self.hash(e164),
            encrypted=self._fernet.encrypt(e164.encode()),
            last4=e164[-4:],
        )

    def reveal(self, encrypted: bytes) -> str:
        try:
            return self._fernet.decrypt(encrypted).decode()
        except InvalidToken:
            raise RuntimeError("Phone number could not be decrypted. Check DATA_ENCRYPTION_KEY.")