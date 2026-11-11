"""Email providers. "console" logs instead of sending (development); "resend" sends through Resend's API."""
import logging
import uuid
from typing import Protocol

import httpx

logger = logging.getLogger("rebookly.notifications")


class SendError(Exception):
    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent   # e.g. an invalid address: retrying won't help


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, text: str, html: str) -> str: ...
    async def close(self) -> None: ...


def mask_email(address: str) -> str:
    """'priya.sharma@example.com' -> 'p***@example.com' (for logs)."""
    name, _, domain = address.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


class ConsoleEmailSender:
    """Development: write the email to the server log instead of sending it."""

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str:
        logger.info("EMAIL to %s | %s\n%s", mask_email(to), subject, text)
        return f"console-{uuid.uuid4().hex[:12]}"

    async def close(self) -> None:
        return None


class ResendEmailSender:
    URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_address: str, timeout: float = 15.0):
        if not api_key or not from_address:
            raise ValueError("RESEND_API_KEY and EMAIL_FROM are required for Resend")
        self._from = from_address
        self._http = httpx.AsyncClient(headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)

    async def send(self, *, to: str, subject: str, text: str, html: str) -> str:
        try:
            response = await self._http.post(self.URL, json={
                "from": self._from, "to": [to], "subject": subject, "text": text, "html": html})
        except httpx.HTTPError as err:
            raise SendError(f"Email provider unreachable: {type(err).__name__}")
        if response.status_code >= 400:
            permanent = 400 <= response.status_code < 500 and response.status_code != 429
            raise SendError(f"Email provider returned {response.status_code}: {response.text[:150]}", permanent)
        return str(response.json().get("id", ""))

    async def close(self) -> None:
        await self._http.aclose()