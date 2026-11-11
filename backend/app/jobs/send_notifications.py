"""Send messages waiting in the outbox; retry failures with growing delays."""
from sqlalchemy import select

from app.clock import get_clock
from app.db import session_scope
from app.models import Notification
from app.notifications.rules import next_attempt
from app.notifications.senders import EmailSender, SendError
from app.notifications.templates import render

BATCH = 50


async def run(sender: EmailSender) -> int:
    now = get_clock().now()
    async with session_scope() as session:
        ids = list(await session.scalars(select(Notification.id).where(
            Notification.status == "pending", Notification.channel == "email",
            Notification.next_attempt_at <= now).order_by(Notification.next_attempt_at).limit(BATCH)))
    sent = 0
    for notification_id in ids:
        async with session_scope() as session:
            note = await session.scalar(select(Notification).where(
                Notification.id == notification_id, Notification.status == "pending").with_for_update(skip_locked=True))
            if note is None:
                continue
            note.attempts += 1
            try:
                subject, text, html = render(note.kind, note.payload)
                note.provider_message_id = await sender.send(to=note.to_address, subject=subject, text=text, html=html)
                note.status, note.sent_at, note.last_error = "sent", get_clock().now(), None
                sent += 1
            except SendError as err:
                retry_at = None if err.permanent else next_attempt(note.attempts, get_clock().now())
                note.last_error = str(err)[:300]
                if retry_at is None:
                    note.status = "failed"
                else:
                    note.next_attempt_at = retry_at
            except ValueError as err:   # e.g. an unknown kind: retrying won't help
                note.status, note.last_error = "failed", str(err)[:300]
            await session.commit()
    return sent