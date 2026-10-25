"""Tests for service money rules and the policy preview (no database needed)."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.policy import PolicyDraftIn
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.policies import build_preview, holds_for, policy_warnings, to_engine_policy

RULES = {
    "free_cancel_hours": 24,
    "late_cancel_fee": {"kind": "percent_of_hold", "value": "50"},
    "no_show_fee": {"kind": "percent_of_hold", "value": "100"},
    "waive_if_refilled": True,
    "grace_minutes": 10,
}


def service(**fields):
    base = dict(name="1:1 session", duration_minutes=60, price="45", deposit="20")
    base.update(fields)
    return ServiceCreate(**base)


# ---------- services ----------

def test_valid_service_defaults_to_deposit_held():
    assert service().payment_options == ["deposit_held"]


@pytest.mark.parametrize("fields", [
    {"deposit": "50"},                                         # deposit above price
    {"deposit": "0"},                                          # deposit option needs a deposit
    {"price": "0", "deposit": "0", "payment_options": ["full_held"]},  # full hold needs a price
    {"price": "45.999"},                                       # more than 2 decimals
    {"duration_minutes": 2},                                   # too short
    {"payment_options": []},                                   # no payment option
    {"payment_options": ["deposit_held", "deposit_held"]},     # duplicate
    {"payment_options": ["pay_now"]},                          # not in the MVP
    {"is_active": False},                                      # not settable on create
])
def test_invalid_services_are_rejected(fields):
    with pytest.raises(ValidationError):
        service(**fields)


def test_full_hold_only_service_can_have_zero_deposit():
    assert service(deposit="0", payment_options=["full_held"]).deposit == Decimal("0")


def test_service_update_cannot_blank_price():
    with pytest.raises(ValidationError):
        ServiceUpdate(price=None)


def test_holds_for_lists_every_amount_that_could_be_held():
    services = [
        SimpleNamespace(is_active=True, payment_options=["deposit_held", "full_held"],
                        deposit=Decimal("20"), price=Decimal("45")),
        SimpleNamespace(is_active=False, payment_options=["deposit_held"], deposit=Decimal("5"), price=Decimal("10")),
    ]
    assert holds_for(services) == [Decimal("20"), Decimal("45")]


# ---------- policy drafts ----------

def test_policy_draft_accepts_engine_shaped_rules():
    draft = PolicyDraftIn(raw_text="Free cancellation up to 24 hours before.", rules=RULES)
    assert draft.rules.free_cancel_hours == 24


def test_policy_draft_rejects_unknown_rule_fields():
    with pytest.raises(ValidationError):
        PolicyDraftIn(raw_text="x", rules={**RULES, "refund_everything": True})


def test_engine_rejects_impossible_policy():
    with pytest.raises(ValueError):
        to_engine_policy({**RULES, "grace_minutes": 500}, version=1)


# ---------- preview ----------

def preview_rows(rules=RULES, held="20.00"):
    preview = build_preview(to_engine_policy(rules, 1), Decimal(held), [Decimal(held)])
    return {row.situation: row for row in preview.rows}


def test_preview_shows_every_common_situation():
    rows = preview_rows()
    assert rows["Client attends"].outcome == "Applied to the price"
    assert rows["Cancels 48 hours before"].charged == Decimal("0.00")
    assert rows["Cancels 12 hours before"].charged == Decimal("10.00")
    assert rows["Cancels 12 hours before"].released == Decimal("10.00")
    assert rows["Cancels 12 hours before"].needs_owner_approval
    assert rows["Cancels 12 hours before, slot refilled"].charged == Decimal("0.00")
    assert rows["Client 10 min late"].outcome == "Not a no-show yet"
    assert rows["No-show"].charged == Decimal("20.00")
    assert rows["Business cancels"].released == Decimal("20.00")


def test_preview_without_free_window_skips_late_cancellation_rows():
    rows = preview_rows({**RULES, "free_cancel_hours": 0})
    assert not any("refilled" in situation for situation in rows)


def test_warning_when_free_window_exceeds_booking_window():
    warnings = policy_warnings(to_engine_policy({**RULES, "free_cancel_hours": 96}, 1), [])
    assert any("72 hours" in w for w in warnings)


def test_warning_when_fixed_fee_exceeds_smallest_hold():
    rules = {**RULES, "no_show_fee": {"kind": "fixed", "value": "40"}}
    warnings = policy_warnings(to_engine_policy(rules, 1), [Decimal("20"), Decimal("45")])
    assert warnings == [
        "Your no-show fee is 40.00, but your smallest hold is 20.00. "
        "For that service, the most you can collect is 20.00."
    ]


def test_no_warnings_for_sensible_policy():
    assert policy_warnings(to_engine_policy(RULES, 1), [Decimal("20")]) == []