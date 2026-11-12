from decimal import Decimal as D

import pytest

from app.rules.deposits import deposit_for
from app.rules.platform_fee import owner_receives, platform_fee


def fee(**changes):
    facts = dict(amount=D("300.00"), event="attended", action="capture", plan="free", pro_active=False)
    facts.update(changes)
    return platform_fee(**facts)


def test_three_percent_when_a_client_pays_for_a_visit():
    assert fee() == D("9.00")
    assert fee(amount=D("30.00")) == D("0.90")
    assert owner_receives(D("30.00"), fee(amount=D("30.00"))) == D("29.10")


@pytest.mark.parametrize("changes", [
    {"event": "client_cancelled"}, {"event": "owner_cancelled"}, {"event": "no_show"},   # cancellations: never
    {"action": "void"},                                                                  # released hold: no money moved
    {"plan": "pro", "pro_active": True},                                                 # Pro: no per-visit fee
])
def test_no_fee(changes):
    assert fee(**changes) == D("0.00")


def test_lapsed_pro_pays_the_free_plan_fee():
    assert fee(plan="pro", pro_active=False) == D("9.00")


def test_rounding_to_the_paisa():
    assert fee(amount=D("33.33")) == D("1.00")       # 0.9999 -> 1.00


@pytest.mark.parametrize("price, currency, percent, fixed, expected", [
    (D("300"), "INR", D("10"), None, D("30.00")),     # the suggestion
    (D("450"), "INR", D("10"), None, D("45.00")),
    (D("150"), "INR", D("10"), None, D("20.00")),     # 15 is below the ₹20 minimum
    (D("15"), "INR", D("10"), None, D("15.00")),      # never more than the price
    (D("999"), "INR", D("20"), None, D("200.00")),    # 199.8 rounds to whole rupees
    (D("40"), "USD", D("10"), None, D("4.00")),
    (D("300"), "INR", None, D("100"), D("100.00")),   # a fixed amount
    (D("0"), "INR", D("10"), None, D("0.00")),        # free service: no deposit
])
def test_deposit_rule(price, currency, percent, fixed, expected):
    assert deposit_for(price=price, currency=currency, percent=percent, fixed=fixed) == expected
