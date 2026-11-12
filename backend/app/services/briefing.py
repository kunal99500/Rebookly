"""The owner's daily briefing: facts gathered by code, a short summary written by the AI (checked), saved per day."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts
from app.ai.client import AIClient, AIUnavailable
from app.clock import get_clock
from app.models import Booking, Business, DailyBriefing, Decision, Review, Staff, WaitlistEntry
from app.rules.briefing import BriefingFacts, highlights, plain_summary, suggestions, summary_is_grounded
from app.rules.formatting import money

MAX_REFRESHES = 3


class BriefingOut(BaseModel):
    day: str
    summary: str
    ai_written: bool
    highlights: list[str]
    suggestions: list[str]
    numbers: dict
    generated_at: datetime
    refreshes_left: int


def _clock_label(moment: datetime, tz: ZoneInfo) -> str:
    return moment.astimezone(tz).strftime("%I:%M %p").lstrip("0")


async def gather(session: AsyncSession, business: Business, now: datetime) -> BriefingFacts:
    tz = ZoneInfo(business.timezone)
    local_today = now.astimezone(tz).date()
    day_start = datetime.combine(local_today, datetime.min.time(), tz)
    day_end, yesterday_start = day_start + timedelta(days=1), day_start - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    of_business = Booking.business_id == business.id

    today = list(await session.scalars(select(Booking).where(
        of_business, Booking.status.in_(("confirmed", "attended")),
        Booking.starts_at >= day_start, Booking.starts_at < day_end).order_by(Booking.starts_at)))
    load = (await session.execute(select(Staff.name, func.count(Booking.id)).join(Booking, Booking.staff_id == Staff.id)
                                  .where(Booking.id.in_([b.id for b in today])).group_by(Staff.name)
                                  .order_by(func.count(Booking.id).desc()))).all() if today else []
    waiting = (await session.execute(select(func.count(Decision.id), func.coalesce(func.sum(Decision.amount), 0))
                                     .join(Booking, Booking.id == Decision.booking_id)
                                     .where(of_business, Decision.status == "pending_approval"))).one()
    problems = await session.scalar(select(func.count(Decision.id)).join(Booking, Booking.id == Decision.booking_id)
                                    .where(of_business, Decision.status == "failed"))
    yesterday = dict((await session.execute(select(Booking.status, func.count()).where(
        of_business, Booking.starts_at >= yesterday_start, Booking.starts_at < day_start)
        .group_by(Booking.status))).all())
    waitlist_today = await session.scalar(select(func.count()).select_from(WaitlistEntry).where(
        WaitlistEntry.business_id == business.id, WaitlistEntry.wanted_date == local_today,
        WaitlistEntry.status.in_(("waiting", "offered"))))
    recovered = await session.scalar(select(func.count()).select_from(WaitlistEntry).where(
        WaitlistEntry.business_id == business.id, WaitlistEntry.status == "booked",
        WaitlistEntry.updated_at >= week_ago))
    new_reviews = await session.scalar(select(func.count()).select_from(Review).where(
        Review.business_id == business.id, Review.created_at >= week_ago))

    return BriefingFacts(
        day_label=now.astimezone(tz).strftime("%A %d %B").replace(" 0", " "),
        today_count=len(today),
        first_start=_clock_label(today[0].starts_at, tz) if today else None,
        last_end=_clock_label(max(b.ends_at for b in today), tz) if today else None,
        staff_load=[(name, count) for name, count in load],
        held_today=money(sum((b.held_amount for b in today if b.status == "confirmed"), 0), business.currency),
        fees_waiting=waiting[0], fees_waiting_amount=money(waiting[1], business.currency),
        payment_problems=problems or 0, waitlist_today=waitlist_today or 0,
        yesterday_attended=yesterday.get("attended", 0), yesterday_no_shows=yesterday.get("no_show", 0),
        yesterday_cancelled=yesterday.get("cancelled", 0), recovered_7_days=recovered or 0,
        new_reviews_7_days=new_reviews or 0,
        rating_average=f"{business.rating_average:.1f}" if business.rating_average is not None else None,
    )


async def _summary(ai: AIClient | None, facts: BriefingFacts, business: Business) -> tuple[str, bool]:
    if ai is not None:
        try:
            text = await ai.complete_text(feature="owner_briefing", system=prompts.render("briefing"),
                                          user=str(facts.as_dict()), tier="fast", actor_type="system",
                                          business_id=business.id)
            if text and len(text) <= 600 and summary_is_grounded(text, facts):
                return text, True
        except AIUnavailable:
            pass
    return plain_summary(facts), False


def _out(row: DailyBriefing) -> BriefingOut:
    return BriefingOut(**row.content, ai_written=row.ai_written, generated_at=row.generated_at,
                       refreshes_left=max(MAX_REFRESHES - row.refreshes, 0))


async def get_briefing(session: AsyncSession, ai: AIClient | None, business: Business,
                       refresh: bool = False) -> BriefingOut:
    now = get_clock().now()
    today = now.astimezone(ZoneInfo(business.timezone)).date()
    row = await session.scalar(select(DailyBriefing).where(
        DailyBriefing.business_id == business.id, DailyBriefing.day == today).with_for_update())
    if row is not None and not refresh:
        return _out(row)
    if row is not None and row.refreshes >= MAX_REFRESHES:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You've refreshed today's briefing a few times already.")

    facts = await gather(session, business, now)
    summary, ai_written = await _summary(ai, facts, business)
    content = {"day": facts.day_label, "summary": summary, "highlights": highlights(facts),
               "suggestions": suggestions(facts), "numbers": facts.as_dict()}
    if row is None:
        row = DailyBriefing(business_id=business.id, day=today, content=content, ai_written=ai_written, generated_at=now)
        session.add(row)
    else:
        row.content, row.ai_written, row.generated_at, row.refreshes = content, ai_written, now, row.refreshes + 1
    await session.commit()
    await session.refresh(row)
    return _out(row)