"""Tests for the owner's daily briefing (no database or AI needed)."""
from app.rules.briefing import BriefingFacts, highlights, plain_summary, suggestions, summary_is_grounded

BUSY = BriefingFacts(day_label="Thursday 12 November", today_count=7, first_start="9:30 AM", last_end="6:00 PM",
                     staff_load=[("Anna", 5), ("Ben", 2)], held_today="₹560.00", fees_waiting=2,
                     fees_waiting_amount="₹80.00", payment_problems=1, waitlist_today=3, yesterday_attended=6,
                     yesterday_no_shows=2, yesterday_cancelled=1, recovered_7_days=2, new_reviews_7_days=4,
                     rating_average="4.6")
QUIET = BriefingFacts(day_label="Sunday 15 November", today_count=0, first_start=None, last_end=None)


def test_highlights_state_the_facts():
    lines = highlights(BUSY)
    assert lines[0] == "7 appointments today, from 9:30 AM to 6:00 PM. ₹560.00 in deposits held."
    assert "Busiest: Anna (5), Ben (2)." in lines
    assert "2 fees waiting for your approval (up to ₹80.00)." in lines
    assert "Yesterday: 6 attended, 2 no-shows, 1 cancelled." in lines
    assert "The waitlist refilled 2 cancelled times this week." in lines


def test_quiet_day():
    assert highlights(QUIET) == ["No appointments today."]
    assert any("booking link" in tip for tip in suggestions(QUIET))
    assert plain_summary(QUIET).startswith("Good morning. Sunday 15 November has no appointments")


def test_suggestions_follow_the_facts():
    tips = " ".join(suggestions(BUSY))
    assert "Approvals" in tips and "3 people are on today's waitlist" in tips and "larger deposit" in tips


def test_ai_text_with_only_real_numbers_is_accepted():
    assert summary_is_grounded("Busy Thursday: 7 appointments from 9:30 AM, and 2 fees to decide (₹80.00).", BUSY)


def test_ai_text_with_an_invented_number_is_rejected():
    assert not summary_is_grounded("You'll earn ₹5,000 today from 7 appointments!", BUSY)
    assert not summary_is_grounded("15 appointments today.", BUSY)


def test_plain_summary_reads_naturally():
    assert plain_summary(BUSY) == ("Good morning. Thursday 12 November: 7 appointments, starting at 9:30 AM. "
                                   "2 fees need your decision.")