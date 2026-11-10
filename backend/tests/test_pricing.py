"""Tests for combining services into one visit: time, price, hold and policy."""
from decimal import Decimal

import pytest

from app.rules.pricing import ServiceLine, VisitError, plan_visit, strictest_policy

D = Decimal
BOTH = ("deposit_held", "full_held")


def line(sid, kind="main", minutes=30, cleanup=0, price="20", deposit="5", options=BOTH):
    return ServiceLine(sid, sid.title(), kind, minutes, cleanup, D(price), D(deposit), options)


HAIRCUT = line("haircut")
WASH = line("wash", kind="add_on", minutes=15, price="5", deposit="0")
BEARD = line("beard", kind="add_on", minutes=20, cleanup=5, price="10", deposit="2")


def test_haircut_wash_and_beard_add_up():
    plan = plan_visit([WASH, HAIRCUT, BEARD])
    assert [l.service_id for l in plan.lines] == ["haircut", "wash", "beard"]   # main first
    assert plan.duration_minutes == 65
    assert plan.occupied_minutes == 70          # + longest cleanup
    assert plan.price == D("35") and plan.deposit == D("7")
    assert plan.hold_for("deposit_held") == D("7")
    assert plan.hold_for("full_held") == D("35")


def test_add_on_alone_is_refused():
    with pytest.raises(VisitError, match="main service"):
        plan_visit([WASH])


def test_duplicate_services_are_refused():
    with pytest.raises(VisitError, match="once"):
        plan_visit([HAIRCUT, HAIRCUT])


def test_empty_choice_is_refused():
    with pytest.raises(VisitError):
        plan_visit([])


def test_payment_options_are_those_all_services_allow():
    colour = line("colour", minutes=90, options=("full_held",))
    plan = plan_visit([HAIRCUT, colour])
    assert plan.payment_options == ("full_held",)
    with pytest.raises(VisitError):
        plan.hold_for("deposit_held")


def test_no_deposit_means_no_deposit_option():
    assert plan_visit([line("trim", deposit="0")]).payment_options == ("full_held",)


def test_incompatible_payment_options_are_refused():
    a = line("a", options=("deposit_held",))
    b = line("b", options=("full_held",))
    with pytest.raises(VisitError, match="separately"):
        plan_visit([a, b])


def test_overly_long_visit_is_refused():
    with pytest.raises(VisitError, match="too long"):
        plan_visit([line("marathon", minutes=721)])


def test_strictest_policy_wins():
    business = {"free_cancel_hours": 24}
    photo_shoot = {"free_cancel_hours": 72}
    assert strictest_policy(business, [None, photo_shoot]) is photo_shoot
    assert strictest_policy(business, [None, None]) is business