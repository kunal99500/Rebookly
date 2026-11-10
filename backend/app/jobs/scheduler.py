"""Starts and stops the background jobs.

Each job is safe to run on several servers at once (rows are locked with SKIP LOCKED),
and a slow run never overlaps itself (max_instances=1).
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs import expire_unpaid, recover_payments
from app.payments.paypal import PayPalClient

logger = logging.getLogger("rebookly.jobs")


class JobRunner:
    def __init__(self, paypal: PayPalClient | None):
        self.paypal = paypal

    async def expire_unpaid(self) -> int:
        try:
            count = await expire_unpaid.run()
            if count:
                logger.info("Released %s unpaid booking(s)", count)
            return count
        except Exception:
            logger.exception("expire_unpaid failed")
            return 0

    async def recover_payments(self) -> int:
        if self.paypal is None:
            return 0
        try:
            count = await recover_payments.run(self.paypal)
            if count:
                logger.info("Checked %s stuck payment decision(s)", count)
            return count
        except Exception:
            logger.exception("recover_payments failed")
            return 0

    async def run_all(self) -> dict[str, int]:
        """Run every job once, now. Used by the dev endpoint for demos and testing."""
        return {"expired_bookings": await self.expire_unpaid(), "recovered_decisions": await self.recover_payments()}


def start_scheduler(runner: JobRunner) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(runner.expire_unpaid, "interval", minutes=1, id="expire_unpaid",
                      max_instances=1, coalesce=True)
    scheduler.add_job(runner.recover_payments, "interval", minutes=5, id="recover_payments",
                      max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler