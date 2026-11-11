"""Tests for AI onboarding with a fake AI: drafts are validated by the real setup rules."""
import copy
import json

import pytest
from pydantic import ValidationError

from app.ai.client import AIOutputError
from app.ai.fake import FakeAI
from app.ai.onboarding import (
    MAX_INTERVIEW_ROUNDS, InterviewReply, OnboardingAnswer, OnboardingDraft, OnboardingRequest, draft_setup, interview,
)

GOOD = {
    "business": {"name": "Ravi's Barbershop", "description": "Classic cuts and beard trims in Bandra.",
                 "category": "barber", "timezone": "Asia/Kolkata", "currency": "INR",
                 "phone": "+91 98765 43210", "address": "Somewhere invented", "latitude": None, "longitude": None},
    "services": [
        {"name": "Haircut", "kind": "main", "booking_mode": "appointment", "duration_minutes": 30,
         "cleanup_minutes": 0, "price": "300", "deposit": "80", "payment_options": ["deposit_held", "full_held"]},
        {"name": "Hair wash", "kind": "add_on", "booking_mode": "appointment", "duration_minutes": 15,
         "cleanup_minutes": 0, "price": "100", "deposit": "0", "payment_options": ["full_held"]},
    ],
    "hours": {"hours": [{"weekday": 0, "start": "10:00", "end": "20:00"}]},
    "policy": {"raw_text": "Free cancellation up to 24 hours before. Late cancellations pay half the deposit.",
               "rules": {"free_cancel_hours": 24, "late_cancel_fee": {"kind": "percent_of_hold", "value": "50"},
                         "no_show_fee": {"kind": "percent_of_hold", "value": "100"},
                         "waive_if_refilled": True, "grace_minutes": 10}},
    "needs_confirmation": ["Price for Hair wash is an estimate"],
    "questions": ["Do you take walk-ins?"],
}
REQUEST = OnboardingRequest(description="Barbershop in Bandra, haircuts 300 rupees, open Mondays 10 to 8.",
                            country_code="IN", currency="INR", timezone="Asia/Kolkata")


def reply(**changes):
    """GOOD as JSON, with some values changed. Paths use __ between keys, e.g. services__0__kind."""
    data = copy.deepcopy(GOOD)
    for path, value in changes.items():
        target = data
        *parents, last = path.split("__")
        for key in parents:
            target = target[int(key)] if key.isdigit() else target[key]
        target[int(last) if last.isdigit() else last] = value
    return json.dumps(data)


# ---------- the draft ----------

@pytest.mark.asyncio
async def test_draft_is_built_from_the_description():
    ai = FakeAI([reply()])
    out = await draft_setup(ai, REQUEST, owner_id="owner-1")
    assert out.draft.business.category == "barber"
    assert [s.name for s in out.draft.services] == ["Haircut", "Hair wash"]
    assert out.draft.services[1].kind == "add_on"
    # the request's own settings and description reach the AI
    system, user = ai.requests[0]["messages"][0]["content"], ai.requests[0]["messages"][1]["content"]
    assert "INR" in system and "Asia/Kolkata" in system and "barber" in system
    assert "Bandra" in user and ai.requests[0]["model"] == "fake-smart"


@pytest.mark.asyncio
async def test_invented_contact_details_are_removed():
    out = await draft_setup(FakeAI([reply()]), REQUEST, owner_id="owner-1")
    assert out.draft.business.phone is None and out.draft.business.address is None


@pytest.mark.asyncio
async def test_owner_settings_override_the_ai():
    out = await draft_setup(FakeAI([reply(business__currency="USD", business__timezone="UTC")]), REQUEST, "owner-1")
    assert out.draft.business.currency == "INR" and out.draft.business.timezone == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_preview_is_calculated_by_the_rules_engine():
    out = await draft_setup(FakeAI([reply()]), REQUEST, owner_id="owner-1")
    rows = {r.situation: r for r in out.policy_preview.rows}
    assert out.policy_preview.example_hold == 80            # the haircut deposit
    assert rows["No-show"].charged == 80 and rows["Cancels 12 hours before"].charged == 40


@pytest.mark.asyncio
async def test_suggestions_are_flagged():
    out = await draft_setup(FakeAI([reply()]), REQUEST, owner_id="owner-1")
    assert out.draft.needs_confirmation and any("suggestions" in w for w in out.warnings)


@pytest.mark.asyncio
async def test_fixed_fee_bigger_than_deposit_gives_a_warning():
    out = await draft_setup(FakeAI([reply(policy__rules__no_show_fee={"kind": "fixed", "value": "500"})]),
                            REQUEST, owner_id="owner-1")
    assert any("no-show fee is 500.00" in w for w in out.warnings)


@pytest.mark.parametrize("bad, problem", [
    ({"policy__rules__free_cancel_hours": 200}, "Free cancellation"),        # rules engine refuses
    ({"policy__rules__free_cancel_hours": 96}, "at most 72"),                # beyond the booking window
    ({"services__0__kind": "add_on"}, "main service"),                       # only add-ons
    ({"services__1__name": "haircut"}, "different name"),                    # duplicate names
    ({"services__0__deposit": "500"}, "deposit can't be more"),              # real service money rules
    ({"business__category": "spaceship_repair"}, "category"),                # unknown category
])
def test_invalid_drafts_are_rejected_by_the_real_rules(bad, problem):
    with pytest.raises(ValidationError, match=problem):
        OnboardingDraft.model_validate_json(reply(**bad))


@pytest.mark.asyncio
async def test_invalid_reply_is_retried_with_the_problem_explained():
    ai = FakeAI([reply(policy__rules__free_cancel_hours=96), reply()])
    out = await draft_setup(ai, REQUEST, owner_id="owner-1")
    assert out.draft.policy.rules.free_cancel_hours == 24
    assert "at most 72" in ai.requests[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_two_invalid_replies_give_up_cleanly():
    ai = FakeAI([reply(services__0__kind="add_on"), reply(services__0__kind="add_on")])
    with pytest.raises(AIOutputError):
        await draft_setup(ai, REQUEST, owner_id="owner-1")


@pytest.mark.parametrize("fields", [
    {"description": "ab"},                                                                   # too short
    {"description": "A long enough description of my salon.", "timezone": "Mars/Base"},    # unknown time zone
    {"description": "A long enough description of my salon.", "currency": "inr"},          # currency must be uppercase
])
def test_invalid_requests_are_rejected(fields):
    with pytest.raises(ValidationError):
        OnboardingRequest(**fields)


# ---------- the interview: asking politely about anything missing ----------

SHORT = OnboardingRequest(description="I have a barbershop", country_code="IN", currency="INR")

QUESTIONS = {
    "status": "needs_more_info",
    "summary": "You run a barbershop.",
    "missing_topics": ["services", "prices", "opening_hours"],
    "questions": [
        {"id": "services", "topic": "services", "text": "Which of these do you offer?", "kind": "multi_choice",
         "options": ["Haircut", "Beard trim", "Shave", "Kids' haircut", "Hair colour"], "allow_other": True},
        {"id": "haircut_price", "topic": "prices", "text": "How much is a haircut?", "kind": "number"},
        {"id": "hours", "topic": "opening_hours", "text": "When are you open?", "kind": "text"},
    ],
}


def test_short_descriptions_are_allowed_to_start():
    assert SHORT.description == "I have a barbershop"


@pytest.mark.asyncio
async def test_short_description_gets_friendly_questions():
    ai = FakeAI([json.dumps(QUESTIONS)])
    out = await interview(ai, SHORT, round_number=0)
    assert out.status == "needs_more_info" and len(out.questions) == 3
    assert out.questions[0].kind == "multi_choice" and "Beard trim" in out.questions[0].options
    assert out.round == 0 and out.max_rounds == MAX_INTERVIEW_ROUNDS and out.can_skip
    assert ai.requests[0]["model"] == "fake-fast"          # questions use the cheaper model
    assert "round 1 of at most 3" in ai.requests[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_answers_are_sent_back_to_the_ai():
    ai = FakeAI([json.dumps({"status": "ready", "summary": "Barbershop with haircuts and beard trims."})])
    request = SHORT.model_copy(update={"answers": [
        OnboardingAnswer(question="Which of these do you offer?", answer="Haircut, Beard trim"),
        OnboardingAnswer(question="How much is a haircut?", answer="300"),
    ]})
    out = await interview(ai, request, round_number=1)
    assert out.status == "ready" and out.questions == []
    sent = ai.requests[0]["messages"][1]["content"]
    assert "Q: How much is a haircut?" in sent and "A: 300" in sent


@pytest.mark.asyncio
async def test_interview_stops_after_the_last_round_without_calling_the_ai():
    ai = FakeAI([])
    out = await interview(ai, SHORT, round_number=MAX_INTERVIEW_ROUNDS)
    assert out.status == "ready" and ai.requests == []


@pytest.mark.asyncio
async def test_answers_reach_the_draft_too():
    ai = FakeAI([reply()])
    request = REQUEST.model_copy(update={"answers": [OnboardingAnswer(question="Kids' haircuts?", answer="Yes, 200")]})
    await draft_setup(ai, request, owner_id="owner-1")
    assert "Kids' haircuts?" in ai.requests[0]["messages"][1]["content"]


@pytest.mark.parametrize("bad", [
    {"status": "needs_more_info", "summary": "x", "questions": []},                          # asks nothing
    {"status": "needs_more_info", "summary": "x", "questions": [
        {"id": "a", "topic": "services", "text": "Which do you offer?", "kind": "multi_choice", "options": ["Only one"]}]},
    {"status": "needs_more_info", "summary": "x", "questions": [
        {"id": "a", "topic": "prices", "text": "How much is it?", "kind": "number", "options": ["10", "20"]}]},
    {"status": "needs_more_info", "summary": "x", "questions": [
        {"id": "a", "topic": "weather", "text": "Is it sunny today?", "kind": "yes_no"}]},     # not a setup topic
    {"status": "needs_more_info", "summary": "x", "questions": [
        {"id": f"q{i}", "topic": "services", "text": "Another question?", "kind": "yes_no"} for i in range(5)]},
])
def test_badly_formed_questions_are_rejected(bad):
    with pytest.raises(ValidationError):
        InterviewReply.model_validate(bad)