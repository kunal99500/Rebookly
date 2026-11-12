"""Tests for when a client's data can be deleted (no database needed)."""
from app.rules.account_deletion import CONFIRM_WORD, DELETED_NAME, deletion_blockers


def test_nothing_in_progress_means_it_can_be_deleted():
    assert deletion_blockers(upcoming_bookings=0, unpaid_bookings=0, fees_waiting=0) == []


def test_each_blocker_is_explained():
    reasons = deletion_blockers(upcoming_bookings=2, unpaid_bookings=1, fees_waiting=1)
    assert len(reasons) == 3
    assert "2 upcoming booking(s)" in reasons[0]
    assert "waiting for payment" in reasons[1]
    assert "deciding on a fee" in reasons[2]


def test_fixed_words():
    assert DELETED_NAME == "Deleted client" and CONFIRM_WORD == "DELETE"