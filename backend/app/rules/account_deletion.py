"""Deleting a client's data. Pure rules, no database.

What's deleted: name, phone, email, reviews, waitlist entries, and pending messages. The sign-in account
is removed too. What's kept: the bookings, payments and receipts themselves, because businesses must keep
financial records by law; they're no longer linked to any contact details.
"""
DELETED_NAME = "Deleted client"
CONFIRM_WORD = "DELETE"


def deletion_blockers(*, upcoming_bookings: int, unpaid_bookings: int, fees_waiting: int) -> list[str]:
    """Reasons the account can't be deleted yet (money is still held or a visit is still to come)."""
    reasons = []
    if upcoming_bookings:
        reasons.append(f"You have {upcoming_bookings} upcoming booking(s). Cancel them or wait until they're done.")
    if unpaid_bookings:
        reasons.append("You have a booking waiting for payment. Finish or abandon it first (it expires in 15 minutes).")
    if fees_waiting:
        reasons.append("A business is still deciding on a fee for one of your bookings. Try again once it's settled.")
    return reasons