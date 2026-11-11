"""AI onboarding: the owner describes their business in plain words; the AI drafts the setup.

The draft uses EXACTLY the same shapes as the normal setup API (BusinessCreate, ServiceCreate,
AvailabilityIn, PolicyDraftIn), so every suggestion passes the same validation as typed input.
Nothing is saved here. The owner reviews and edits the draft, then applies it.
"""
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.ai import prompts
from app.ai.client import AIClient
from app.rules.catalog import BOOKING_WINDOW_HOURS, CATEGORIES
from app.schemas.business import BusinessCreate
from app.schemas.policy import PolicyDraftIn, PolicyPreviewOut
from app.schemas.schedule import AvailabilityIn
from app.schemas.service import ServiceCreate
from app.services import policies

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MAX_INTERVIEW_ROUNDS = 3
TOPICS = ("services", "add_ons", "prices", "durations", "opening_hours", "cancellation_policy", "team", "booking_style")


class OnboardingAnswer(BaseModel):
    """One question the assistant asked, and the owner's answer."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=500)


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str = Field(min_length=3, max_length=3000,
                             description="What you offer, in your own words. Even 'I have a barbershop' is fine to start.")
    answers: list[OnboardingAnswer] = Field(default_factory=list, max_length=20,
                                            description="Answers to the assistant's earlier questions")
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        if value is None:
            return None
        BusinessCreate(name="Check", category="other", timezone=value)  # reuse the real time-zone check
        return value


def owner_text(request: OnboardingRequest) -> str:
    """Everything the owner has told us: their description plus every question and answer so far."""
    parts = [f"<description>\n{request.description}\n</description>"]
    if request.answers:
        qa = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in request.answers)
        parts.append(f"<answers>\n{qa}\n</answers>")
    return "\n\n".join(parts)


# ---------- step 1: the short interview ----------

class InterviewQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,40}$")]
    topic: Literal[TOPICS]  # type: ignore[valid-type]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
    kind: Literal["text", "single_choice", "multi_choice", "yes_no", "number"]
    options: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]] = \
        Field(default_factory=list, max_length=8)
    allow_other: bool = False

    @model_validator(mode="after")
    def _options_match_kind(self) -> "InterviewQuestion":
        if self.kind in ("single_choice", "multi_choice") and len(self.options) < 2:
            raise ValueError("Choice questions need at least 2 options")
        if self.kind not in ("single_choice", "multi_choice") and self.options:
            raise ValueError("Only choice questions have options")
        return self


class InterviewReply(BaseModel):
    """What the AI returns: are we ready to draft, and if not, which questions to ask."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["needs_more_info", "ready"]
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    missing_topics: list[Literal[TOPICS]] = Field(default_factory=list, max_length=len(TOPICS))  # type: ignore[valid-type]
    questions: list[InterviewQuestion] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _consistent(self) -> "InterviewReply":
        if self.status == "needs_more_info" and not self.questions:
            raise ValueError("needs_more_info must come with at least one question")
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Each question needs a different id")
        return self


class InterviewRequest(OnboardingRequest):
    round: int = Field(default=0, ge=0, le=10, description="0 for the first call; then the round you got back + 1")


class InterviewOut(InterviewReply):
    round: int                 # this round's number; send round + 1 next time
    max_rounds: int
    can_skip: bool = True      # the owner can always stop and get a draft with suggestions


async def interview(ai: AIClient, request: OnboardingRequest, round_number: int) -> InterviewOut:
    """Ask a few friendly questions about anything important that's missing, or say we're ready."""
    if round_number >= MAX_INTERVIEW_ROUNDS:  # never keep the owner answering questions forever
        return InterviewOut(status="ready", summary="Thanks, that's enough to prepare your setup.",
                            round=round_number, max_rounds=MAX_INTERVIEW_ROUNDS)
    system = prompts.render(
        "onboarding_interview",
        country=(request.country_code or "not given").upper(),
        currency=request.currency or "the local currency",
        round=round_number + 1, max_rounds=MAX_INTERVIEW_ROUNDS,
    )
    reply = await ai.complete_json(feature="onboarding_interview", system=system, user=owner_text(request),
                                   schema=InterviewReply, tier="fast", actor_type="owner")
    if reply.status == "ready":
        reply = reply.model_copy(update={"questions": [], "missing_topics": []})
    return InterviewOut(**reply.model_dump(), round=round_number, max_rounds=MAX_INTERVIEW_ROUNDS)


# ---------- step 2: the draft ----------

class OnboardingDraft(BaseModel):
    """A complete first setup. Each part is exactly what the matching setup endpoint accepts."""
    model_config = ConfigDict(extra="forbid")

    business: BusinessCreate
    services: list[ServiceCreate] = Field(min_length=1, max_length=20)
    hours: AvailabilityIn | None = None
    policy: PolicyDraftIn
    needs_confirmation: list[ShortText] = Field(default_factory=list, max_length=10)
    questions: list[ShortText] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _consistent(self) -> "OnboardingDraft":
        if not any(s.kind == "main" for s in self.services):
            raise ValueError("At least one service must be a main service (add-ons need one)")
        names = [s.name.casefold() for s in self.services]
        if len(set(names)) != len(names):
            raise ValueError("Each service needs a different name")
        rules = self.policy.rules.model_dump(mode="json")
        policies.to_engine_policy(rules, version=1)  # the rules engine's own checks
        if self.policy.rules.free_cancel_hours > BOOKING_WINDOW_HOURS:
            raise ValueError(f"free_cancel_hours must be at most {BOOKING_WINDOW_HOURS}")
        return self


class OnboardingDraftOut(BaseModel):
    draft: OnboardingDraft
    warnings: list[str]
    policy_preview: PolicyPreviewOut   # calculated by the rules engine, not the AI


def finalize(draft: OnboardingDraft, request: OnboardingRequest) -> tuple[OnboardingDraft, list[str]]:
    """Deterministic clean-up after the AI: owner-given settings win, and no invented contact details."""
    business_updates = {"phone": None, "address": None, "latitude": None, "longitude": None}
    if request.timezone:
        business_updates["timezone"] = request.timezone
    if request.currency:
        business_updates["currency"] = request.currency
    business = BusinessCreate.model_validate({**draft.business.model_dump(), **business_updates})
    draft = draft.model_copy(update={"business": business})

    engine_policy = policies.to_engine_policy(draft.policy.rules.model_dump(mode="json"), version=1)
    warnings = policies.policy_warnings(engine_policy, _holds(draft))
    if draft.needs_confirmation:
        warnings.append("Some details are suggestions. Check everything marked under needs_confirmation.")
    return draft, warnings


def preview(draft: OnboardingDraft) -> PolicyPreviewOut:
    engine_policy = policies.to_engine_policy(draft.policy.rules.model_dump(mode="json"), version=1)
    holds = _holds(draft)
    return policies.build_preview(engine_policy, holds[0] if holds else policies.DEFAULT_EXAMPLE_HOLD, holds)


def _holds(draft: OnboardingDraft):
    as_services = [SimpleNamespace(is_active=True, payment_options=s.payment_options, deposit=s.deposit, price=s.price)
                   for s in draft.services if s.kind == "main"]
    return policies.holds_for(as_services)


async def draft_setup(ai: AIClient, request: OnboardingRequest, owner_id) -> OnboardingDraftOut:
    system = prompts.render(
        "onboarding",
        country=(request.country_code or "not given").upper(),
        currency=request.currency or "not given (choose the usual currency for the country, ISO code like USD)",
        timezone=request.timezone or "not given (choose the likely IANA time zone, e.g. Asia/Kolkata)",
        categories=", ".join(CATEGORIES),
    )
    draft = await ai.complete_json(feature="onboarding", system=system, user=owner_text(request), schema=OnboardingDraft,
                                   tier="smart", actor_type="owner")
    draft, warnings = finalize(draft, request)
    return OnboardingDraftOut(draft=draft, warnings=warnings, policy_preview=preview(draft))