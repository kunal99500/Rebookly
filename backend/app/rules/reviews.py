"""Review rules: who may review, when, and what a comment may contain. Pure functions, no database."""
import re
from datetime import datetime, timedelta

REVIEW_WINDOW = timedelta(days=30)      # after the visit
EDIT_WINDOW = timedelta(days=7)         # after writing the review
MAX_COMMENT = 1000

_URL = re.compile(r"(https?://|www\.)\S+|\b[a-z0-9-]+\.(com|in|net|org|io|co|app|me|link)\b", re.IGNORECASE)
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", re.IGNORECASE)
_PHONE = re.compile(r"(?:\+?\d[\s().-]*){8,}")


def review_problem(*, booking_status: str, visit_ended_at: datetime, now: datetime, already_reviewed: bool) -> str | None:
    """None if this booking can be reviewed now, otherwise the reason (in plain words)."""
    if already_reviewed:
        return "You've already reviewed this visit. You can edit your review instead."
    if booking_status != "attended":
        return "Only visits you attended can be reviewed."
    if now > visit_ended_at + REVIEW_WINDOW:
        return "Reviews can be written up to 30 days after the visit."
    return None


def can_edit(written_at: datetime, now: datetime) -> bool:
    return now <= written_at + EDIT_WINDOW


def comment_problem(comment: str | None) -> str | None:
    """Comments can't share links, emails or phone numbers (no spam, no contact details)."""
    if not comment:
        return None
    if _EMAIL.search(comment):
        return "Please don't include email addresses in reviews."
    if _URL.search(comment):
        return "Please don't include links in reviews."
    if _PHONE.search(comment):
        return "Please don't include phone numbers in reviews."
    return None


def display_name(full_name: str | None) -> str:
    """'Priya Sharma' -> 'Priya S.'; reviewers are shown by first name and initial only."""
    parts = (full_name or "").split()
    if not parts:
        return "A client"
    return f"{parts[0]} {parts[-1][0].upper()}." if len(parts) > 1 else parts[0]