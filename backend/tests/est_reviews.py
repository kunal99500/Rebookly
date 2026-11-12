"""Tests for review rules (no database needed)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.rules.reviews import can_edit, comment_problem, display_name, review_problem

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def problem(**changes):
    facts = dict(booking_status="attended", visit_ended_at=NOW - timedelta(days=2), now=NOW, already_reviewed=False)
    facts.update(changes)
    return review_problem(**facts)


def test_attended_visit_can_be_reviewed():
    assert problem() is None


@pytest.mark.parametrize("changes, reason", [
    ({"booking_status": "confirmed"}, "Only visits you attended"),
    ({"booking_status": "no_show"}, "Only visits you attended"),
    ({"booking_status": "cancelled"}, "Only visits you attended"),
    ({"visit_ended_at": NOW - timedelta(days=31)}, "up to 30 days"),
    ({"already_reviewed": True}, "already reviewed"),
])
def test_who_cannot_review(changes, reason):
    assert reason in problem(**changes)


def test_edit_window():
    assert can_edit(NOW - timedelta(days=6), NOW) and not can_edit(NOW - timedelta(days=8), NOW)


@pytest.mark.parametrize("comment", [
    None, "", "Great fade, Ravi was quick and friendly!", "Booked at 4:30, done by 5.", "5 stars, 10/10 would return",
])
def test_normal_comments_are_fine(comment):
    assert comment_problem(comment) is None


@pytest.mark.parametrize("comment, reason", [
    ("Email me at priya@example.com", "email"),
    ("Better deals at www.cheapcuts.in", "links"),
    ("see https://spam.example", "links"),
    ("Call +91 98765 43210 for discounts", "phone"),
])
def test_contact_details_and_links_are_refused(comment, reason):
    assert reason in comment_problem(comment)


@pytest.mark.parametrize("name, shown", [("Priya Sharma", "Priya S."), ("Asha", "Asha"),
                                         ("  ravi kumar singh ", "ravi S."), ("", "A client"), (None, "A client")])
def test_reviewers_are_shown_by_first_name_and_initial(name, shown):
    assert display_name(name) == shown