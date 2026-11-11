"""Starts and stops the background jobs.

Each job is safe to run on several servers at once (rows are locked with SKIP LOCKED),
and a slow run never overlaps itself (max_instances=1).
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import session_scope
from app.jobs import expire_unpaid, recover_payments, send_notifications, send_reminders
from app.notifications.senders import EmailSender
from app.payments import webhooks
from app.payments.paypal import PayPalClient
from app.services import outcomes, refills, waitlist

logger = logging.getLogger("rebookly.jobs")


class JobRunner:
    def __init__(self, paypal: PayPalClient | None, email_sender: EmailSender | None = None):
        self.paypal = paypal
        self.email_sender = email_sender

    async def _safe(self, name: str, job) -> int:
        """Run one job; a failure is logged and the job simply runs again next time."""
        try:
            count = await job()
            if count:
                logger.info("%s: %s", name, count)
            return count
        except Exception:
            logger.exception("%s failed", name)
            return 0

    async def expire_unpaid(self) -> int:
        return await self._safe("expire_unpaid", expire_unpaid.run)

    async def recover_payments(self) -> int:
        if self.paypal is None:
            return 0
        return await self._safe("recover_payments", lambda: recover_payments.run(self.paypal))

    async def retry_webhooks(self) -> int:
        if self.paypal is None:
            return 0
        return await self._safe("retry_webhooks", lambda: webhooks.retry_failed(session_scope, self.paypal))

    async def settle_refills(self) -> int:
        """Late-cancellation fees whose time was rebooked: release the hold if the policy says so."""
        if self.paypal is None:
            return 0

        async def job() -> int:
            async with session_scope() as session:
                waiting = await refills.pending_late_cancellations(session)
            released = 0
            for decision_id in waiting:
                async with session_scope() as session:
                    new_id = await refills.waive_if_refilled(session, decision_id)
                    if new_id is not None:
                        await outcomes.execute(session, self.paypal, new_id)
                        released += 1
            return released

        return await self._safe("settle_refills", job)

    async def tidy_waitlist(self) -> int:
        async def job() -> int:
            async with session_scope() as session:
                return await waitlist.tidy(session)

        return await self._safe("tidy_waitlist", job)

    async def send_notifications(self) -> int:
        if self.email_sender is None:
            return 0
        return await self._safe("send_notifications", lambda: send_notifications.run(self.email_sender))

    async def send_reminders(self) -> int:
        return await self._safe("send_reminders", send_reminders.run)

    async def run_all(self) -> dict[str, int]:
        """Run every job once, now. Used by the dev endpoint for demos and testing."""
        return {
            "expired_bookings": await self.expire_unpaid(),
            "recovered_decisions": await self.recover_payments(),
            "webhooks_retried": await self.retry_webhooks(),
            "fees_waived_after_refill": await self.settle_refills(),
            "waitlist_tidied": await self.tidy_waitlist(),
            "reminders_checked": await self.send_reminders(),
            "notifications_sent": await self.send_notifications(),
        }


def start_scheduler(runner: JobRunner) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    for job, minutes in ((runner.expire_unpaid, 1), (runner.recover_payments, 5), (runner.retry_webhooks, 10),
                         (runner.settle_refills, 5), (runner.tidy_waitlist, 5),
                         (runner.send_reminders, 5), (runner.send_notifications, 1)):
        scheduler.add_job(job, "interval", minutes=minutes, id=job.__name__, max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler