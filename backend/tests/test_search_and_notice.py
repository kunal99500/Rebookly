"""Tests for understanding search words and for the deposit notice (no database needed)."""
from decimal import Decimal as D

import pytest

from app.rules.deposit_notice import build_notice
from app.rules.engine import Fee, FeeKind
from app.rules.search_terms import understand


@pytest.mark.parametrize("query, category, near_me", [
    ("barber shop near me", "barber", True),
    ("barber shop", "barber", False),
    ("Barbershop", "barber", False),
    ("haircut nearby", "barber", True),
    ("nails", "nail_studio", False),
    ("yoga class near me", "fitness_class", True),
    ("Ravi's", None, False),                       # a name: no category, matched by name instead
])
def test_understanding_search_words(query, category, near_me):
    intent = understand(query)
    assert (intent.category, intent.near_me) == (category, near_me)


def test_leftover_words_are_kept_for_name_matching():
    assert understand("best beard trim near me").words == ("beard", "trim")
    assert "ravi" in understand("Ravi's barbershop").words


def test_empty_search():
    intent = understand("   ")
    assert intent.category is None and intent.words == ()


HALF, FULL = Fee(FeeKind.PERCENT_OF_HOLD, D("50")), Fee(FeeKind.PERCENT_OF_HOLD, D("100"))


def notice(**changes):
    base = dict(hold=D("80"), total=D("400"), currency="INR", payment_option="deposit_held",
                free_cancel_hours=24, late_cancel_fee=HALF, no_show_fee=FULL)
    base.update(changes)
    return build_notice(**base)


def test_deposit_notice_states_the_real_amounts():
    n = notice()
    assert n["summary"].startswith("₹80.00 will be held")
    assert n["lines"] == [{"label": "Held now (not charged)", "amount": "₹80.00"},
                          {"label": "Pay at the business", "amount": "₹320.00"}]
    assert n["policy"] == ["Free cancellation up to 24 hours before.", "Late cancellation keeps ₹40.00.",
                           "Not showing up keeps ₹80.00."]


def test_full_amount_held_has_nothing_to_pay_later():
    assert notice(hold=D("400"), payment_option="full_held")["lines"][1]["label"] == "Nothing more to pay later"


def test_fees_are_capped_at_the_hold():
    n = notice(late_cancel_fee=Fee(FeeKind.FIXED, D("500")))
    assert "Late cancellation keeps ₹80.00." in n["policy"]


def test_no_fees_policy_reads_clearly():
    n = notice(free_cancel_hours=0, late_cancel_fee=Fee(FeeKind.FIXED, D("0")), no_show_fee=Fee(FeeKind.FIXED, D("0")))
    assert n["policy"] == ["Cancelling is free.", "No fee for not showing up."]


def test_owner_note_is_kept_but_never_replaces_the_amounts():
    n = notice(owner_note="Please arrive 5 minutes early.")
    assert n["owner_note"] == "Please arrive 5 minutes early." and n["lines"][0]["amount"] == "₹80.00"