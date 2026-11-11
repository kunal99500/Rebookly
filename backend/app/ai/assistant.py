"""The client assistant: a chat that answers booking questions using permission-checked tools.

The AI can look things up and PREPARE a change (a move or a cancellation). It can't make the change:
prepared changes are returned as "actions", which the app shows as cards the client confirms with a tap.
Confirming calls the normal reschedule / cancel endpoints, with all their rules. No money moves here.
"""
import time
import uuid
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.ai import prompts
from app.ai.client import AIClient, Tool, ToolError
from app.clock import get_clock

ASSISTANT_TIER = "fast"
MAX_MESSAGES = 20
MESSAGES_PER_HOUR = 40


# ---------- what the app sends and gets back ----------

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES,
                                        description="The conversation so far, oldest first, ending with the client")
    business_slug: str | None = Field(default=None, max_length=80, description="Set when chatting on a business page")
    timezone: str | None = Field(default=None, max_length=64, description="The client's time zone, e.g. Asia/Kolkata")

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except Exception:
            raise ValueError("Unknown time zone")
        return value


class ProposedAction(BaseModel):
    """A change the client can confirm with one tap. The app calls the normal endpoint to do it."""
    type: Literal["reschedule", "cancel"]
    booking_id: uuid.UUID
    starts_at: datetime | None = None      # new time, for reschedule
    title: str                             # e.g. "Move Haircut to Fri 14 Nov, 4:30 PM"
    details: str                           # e.g. "Same deposit, same policy." or "Fee: ₹40.00, ₹40.00 released"


class AssistantOut(BaseModel):
    reply: str
    actions: list[ProposedAction]


# ---------- the tools' arguments (validated before any tool runs) ----------

Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=20)]


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RefArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: Ref = Field(description="The booking reference, like RB-AB12-CD34")


class OptionsArgs(RefArgs):
    day: date | None = Field(default=None, description="Only this day, YYYY-MM-DD (optional)")


class ProposeMoveArgs(RefArgs):
    starts_at: datetime = Field(description="A start time exactly as returned by reschedule_options")


class BusinessArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=80, description="The business's slug")


class ClientTools:
    """What the assistant may do for ONE signed-in client. Every method checks the booking is theirs.

    The database work lives in services (bookings, outcomes, rescheduling); this class only adapts it
    for the AI and keeps the proposed actions. Tests replace it with fake data.
    """

    def __init__(self):
        self.actions: list[ProposedAction] = []

    async def list_my_bookings(self) -> dict: raise NotImplementedError
    async def cancellation_preview(self, ref: str) -> dict: raise NotImplementedError
    async def reschedule_options(self, ref: str, day: date | None) -> dict: raise NotImplementedError
    async def propose_reschedule(self, ref: str, starts_at: datetime) -> dict: raise NotImplementedError
    async def propose_cancel(self, ref: str) -> dict: raise NotImplementedError
    async def business_info(self, slug: str) -> dict: raise NotImplementedError


def build_tools(tools: ClientTools) -> list[Tool]:
    return [
        Tool("list_my_bookings", "The client's upcoming bookings and those from the last 30 days.",
             NoArgs, lambda a: tools.list_my_bookings()),
        Tool("cancellation_preview", "What cancelling this booking right now would cost, under its agreed policy.",
             RefArgs, lambda a: tools.cancellation_preview(a.ref)),
        Tool("reschedule_options", "Times this booking can move to (same services, same deposit).",
             OptionsArgs, lambda a: tools.reschedule_options(a.ref, a.day)),
        Tool("propose_reschedule", "Prepare moving a booking to one of the reschedule_options times. "
             "The client must confirm it; this does not move it.",
             ProposeMoveArgs, lambda a: tools.propose_reschedule(a.ref, a.starts_at)),
        Tool("propose_cancel", "Prepare cancelling a booking. The client must confirm it; this does not cancel it.",
             RefArgs, lambda a: tools.propose_cancel(a.ref)),
        Tool("business_info", "A business's services, prices, opening hours and cancellation policy.",
             BusinessArgs, lambda a: tools.business_info(a.slug)),
    ]


# ---------- a simple per-client limit, so a chat can't run up costs ----------

class RateLimiter:
    def __init__(self, limit: int = MESSAGES_PER_HOUR, window_seconds: int = 3600):
        self._limit, self._window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


# ---------- one turn of the conversation ----------

async def chat(ai: AIClient, tools: ClientTools, request: AssistantRequest, *, client_name: str,
               timezone: str, business_name: str | None = None) -> AssistantOut:
    if request.messages[-1].role != "user":
        raise ValueError("The last message must be from the client")
    context = (f"\nThe client is on the booking page of {business_name} (slug: {request.business_slug})."
               if business_name else "")
    system = prompts.render("assistant",
                            today=get_clock().now().astimezone(ZoneInfo(timezone)).strftime("%A %d %B %Y, %H:%M"),
                            client_name=client_name or "the client", business_context=context)
    reply = await ai.run_with_tools(
        feature="client_assistant", system=system, tier=ASSISTANT_TIER, actor_type="client",
        messages=[m.model_dump() for m in request.messages], tools=build_tools(tools))
    # Only keep the last proposal per booking (the client may have changed their mind mid-chat).
    latest: dict[uuid.UUID, ProposedAction] = {}
    for action in tools.actions:
        latest[action.booking_id] = action
    return AssistantOut(reply=reply or "Sorry, I couldn't answer that. Please try again.", actions=list(latest.values()))