"""The owner's daily briefing: facts in, highlights, suggestions and a plain summary out. Pure functions.

All numbers come from the database through code. The AI may rephrase the summary, but a guard rejects
any AI text that mentions a number not present in these facts.
"""
import re
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class BriefingFacts:
    day_label: str                         # "Thursday 12 November"
    today_count: int
    first_start: str | None                # "9:30 AM"
    last_end: str | None
    staff_load: list[tuple[str, int]] = field(default_factory=list)   # [("Anna", 5), ("Ben", 2)]
    held_today: str = ""                   # "₹480.00"
    fees_waiting: int = 0
    fees_waiting_amount: str = ""
    payment_problems: int = 0
    waitlist_today: int = 0
    yesterday_attended: int = 0
    yesterday_no_shows: int = 0
    yesterday_cancelled: int = 0
    recovered_7_days: int = 0              # bookings made from waitlist offers
    new_reviews_7_days: int = 0
    rating_average: str | None = None      # "4.6"

    def as_dict(self) -> dict:
        return asdict(self)


def highlights(f: BriefingFacts) -> list[str]:
    lines = []
    if f.today_count:
        lines.append(f"{f.today_count} appointment{'s' if f.today_count != 1 else ''} today, "
                     f"from {f.first_start} to {f.last_end}. {f.held_today} in deposits held.")
        if len(f.staff_load) > 1:
            lines.append("Busiest: " + ", ".join(f"{name} ({n})" for name, n in f.staff_load[:3]) + ".")
    else:
        lines.append("No appointments today.")
    if f.fees_waiting:
        lines.append(f"{f.fees_waiting} fee{'s' if f.fees_waiting != 1 else ''} waiting for your approval "
                     f"(up to {f.fees_waiting_amount}).")
    if f.payment_problems:
        lines.append(f"{f.payment_problems} payment action{'s' if f.payment_problems != 1 else ''} need attention.")
    if f.yesterday_attended or f.yesterday_no_shows or f.yesterday_cancelled:
        lines.append(f"Yesterday: {f.yesterday_attended} attended, {f.yesterday_no_shows} no-show"
                     f"{'s' if f.yesterday_no_shows != 1 else ''}, {f.yesterday_cancelled} cancelled.")
    if f.recovered_7_days:
        lines.append(f"The waitlist refilled {f.recovered_7_days} cancelled time{'s' if f.recovered_7_days != 1 else ''} "
                     "this week.")
    if f.new_reviews_7_days:
        lines.append(f"{f.new_reviews_7_days} new review{'s' if f.new_reviews_7_days != 1 else ''} this week"
                     f"{f', average rating {f.rating_average}' if f.rating_average else ''}.")
    return lines


def suggestions(f: BriefingFacts) -> list[str]:
    tips = []
    if f.fees_waiting:
        tips.append("Review waiting fees in Approvals. If the time was rebooked, the fee is dropped automatically.")
    if f.payment_problems:
        tips.append("Open Approvals and retry the failed payment actions.")
    if f.waitlist_today and f.today_count:
        tips.append(f"{f.waitlist_today} {'people are' if f.waitlist_today != 1 else 'person is'} on today's "
                    "waitlist. Adding hours or another staff member could fill them.")
    if f.yesterday_no_shows >= 2:
        tips.append("Several no-shows yesterday. A larger deposit for those services can help.")
    if not f.today_count and not f.waitlist_today:
        tips.append("A quiet day: sharing your booking link on social media can bring last-minute bookings.")
    return tips


def plain_summary(f: BriefingFacts) -> str:
    """The summary written by code, used when the AI isn't available or its text fails the guard."""
    if not f.today_count:
        return f"Good morning. {f.day_label} has no appointments booked yet."
    extra = (f" {f.fees_waiting} fee{'s need' if f.fees_waiting != 1 else ' needs'} your decision."
             if f.fees_waiting else "")
    return (f"Good morning. {f.day_label}: {f.today_count} appointment{'s' if f.today_count != 1 else ''}, "
            f"starting at {f.first_start}.{extra}")


_NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def summary_is_grounded(text: str, f: BriefingFacts) -> bool:
    """Every number in the AI's text must appear in the facts (so it can't invent counts or amounts)."""
    allowed = numbers_in(" ".join(str(v) for v in _flatten(f.as_dict())))
    return numbers_in(text) <= allowed


def _flatten(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _flatten(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _flatten(v)
    else:
        yield value