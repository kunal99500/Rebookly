"""Tests for the AI client using a fake model: no network, no cost, same behaviour every run."""
import pytest
from pydantic import BaseModel, Field

from app.ai import prompts
from app.ai.client import AIOutputError, AIUnavailable
from app.ai.fake import FakeAI
from app.ai.structured import OutputError, extract_json, parse_output


class Greeting(BaseModel):
    greeting: str = Field(min_length=1)
    word_count: int = Field(ge=1)


GOOD = '{"greeting": "Hello Lumen!", "word_count": 2}'


# ---------- reading replies ----------

def test_plain_and_fenced_json_are_accepted():
    assert extract_json(GOOD)["word_count"] == 2
    assert extract_json(f"```json\n{GOOD}\n```")["greeting"] == "Hello Lumen!"


@pytest.mark.parametrize("text", ["", "hello", "[1, 2]", '{"greeting": "Hi"'])
def test_non_objects_are_rejected(text):
    with pytest.raises(OutputError):
        extract_json(text)


def test_wrong_shape_explains_what_is_wrong():
    with pytest.raises(OutputError, match="word_count"):
        parse_output('{"greeting": "Hi"}', Greeting)


# ---------- the client ----------

@pytest.mark.asyncio
async def test_valid_reply_is_returned_as_an_object():
    ai = FakeAI([GOOD])
    result = await ai.complete_json(feature="ping", system="Say hi.", user="Lumen", schema=Greeting)
    assert result == Greeting(greeting="Hello Lumen!", word_count=2)
    request = ai.requests[0]
    assert request["json_mode"] is True and request["model"] == "fake-smart"
    assert "JSON schema" in request["messages"][0]["content"]   # the schema is always included


@pytest.mark.asyncio
async def test_invalid_reply_is_retried_once_with_the_problem_explained():
    ai = FakeAI(['{"greeting": "Hi"}', GOOD])
    result = await ai.complete_json(feature="ping", system="Say hi.", user="Lumen", schema=Greeting)
    assert result.word_count == 2
    retry_messages = ai.requests[1]["messages"]
    assert retry_messages[-1]["role"] == "user" and "word_count" in retry_messages[-1]["content"]


@pytest.mark.asyncio
async def test_invalid_twice_raises_a_clear_error():
    ai = FakeAI(["nonsense", "still nonsense"])
    with pytest.raises(AIOutputError):
        await ai.complete_json(feature="ping", system="Say hi.", user="Lumen", schema=Greeting)


@pytest.mark.asyncio
async def test_provider_failure_becomes_ai_unavailable():
    ai = FakeAI([TimeoutError("took too long")])
    with pytest.raises(AIUnavailable):
        await ai.complete_json(feature="ping", system="Say hi.", user="Lumen", schema=Greeting)


@pytest.mark.asyncio
async def test_fast_tier_uses_the_fast_model():
    ai = FakeAI(["Hello!"])
    assert await ai.complete_text(feature="hello", system="Be brief.", user="Hi", tier="fast") == "Hello!"
    assert ai.requests[0]["model"] == "fake-fast" and ai.requests[0]["json_mode"] is False


@pytest.mark.asyncio
async def test_every_attempt_is_recorded_with_tokens_and_outcome():
    records = []

    async def record(r):
        records.append(r)

    ai = FakeAI(['{"greeting": "Hi"}', GOOD], record_usage=record)
    await ai.complete_json(feature="ping", system="s", user="u", schema=Greeting, business_id="biz-1", actor_type="owner")
    assert [(r.feature, r.attempt, r.success, r.input_tokens, r.output_tokens) for r in records] == [
        ("ping", 1, True, 100, 20), ("ping", 2, True, 100, 20),
    ]
    assert records[0].business_id == "biz-1" and records[0].actor_type == "owner"
    assert records[0].latency_ms >= 0


@pytest.mark.asyncio
async def test_failed_call_is_recorded_as_failed():
    records = []

    async def record(r):
        records.append(r)

    ai = FakeAI([AIUnavailable("down")], record_usage=record)
    with pytest.raises(AIUnavailable):
        await ai.complete_text(feature="hello", system="s", user="u")
    assert records[0].success is False and records[0].error_type == "provider_unavailable"


# ---------- prompts ----------

def test_prompt_is_filled_in():
    assert "Lumen Fitness" in prompts.render("ping", business_name="Lumen Fitness")


def test_missing_prompt_value_is_an_error():
    with pytest.raises(ValueError, match="business_name"):
        prompts.render("ping")


def test_unknown_prompt_is_an_error():
    with pytest.raises(FileNotFoundError):
        prompts.render("does_not_exist")



# ---------- tools: the AI asks, our code does (with permission checks) ----------

from pydantic import BaseModel as _Model  # noqa: E402

from app.ai.client import Tool, ToolError  # noqa: E402


class _RefArgs(_Model):
    ref: str


def _tools(log):
    async def lookup(args: _RefArgs) -> dict:
        log.append(args.ref)
        if args.ref == "RB-NOPE":
            raise ToolError("No booking with that reference")
        return {"ref": args.ref, "when": "Wed 9:00"}

    async def broken(args: _RefArgs) -> dict:
        class Refused(Exception):
            detail = "Only confirmed bookings can be moved"
        raise Refused()

    return [Tool("lookup_booking", "Find a booking", _RefArgs, lookup),
            Tool("move_booking", "Move a booking", _RefArgs, broken)]


async def _ask(replies, log):
    ai = FakeAI(replies)
    text = await ai.run_with_tools(feature="assistant", system="Be helpful.", tier="smart",
                                   messages=[{"role": "user", "content": "When is my booking?"}], tools=_tools(log))
    return ai, text


@pytest.mark.asyncio
async def test_tool_is_called_and_its_result_reaches_the_ai():
    log = []
    ai, text = await _ask([{"tool_calls": [{"name": "lookup_booking", "arguments": {"ref": "RB-1"}}]},
                           "It's on Wednesday at 9:00."], log)
    assert text == "It's on Wednesday at 9:00." and log == ["RB-1"]
    assert ai.requests[0]["tools"][0]["function"]["name"] == "lookup_booking"
    tool_message = ai.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and "Wed 9:00" in tool_message["content"]


@pytest.mark.parametrize("call, expected", [
    ({"name": "delete_everything", "arguments": {}}, "no tool called"),                 # unknown tool
    ({"name": "lookup_booking", "arguments": {}}, "Invalid arguments"),                 # missing argument
    ({"name": "lookup_booking", "arguments": {"ref": "RB-NOPE"}}, "No booking with that reference"),
    ({"name": "move_booking", "arguments": {"ref": "RB-1"}}, "Only confirmed bookings"),  # service error detail
])
@pytest.mark.asyncio
async def test_tool_problems_are_returned_to_the_ai_as_data(call, expected):
    ai, _ = await _ask([{"tool_calls": [call]}, "Sorry about that."], [])
    assert expected in ai.requests[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_endless_tool_calls_are_cut_off():
    call = {"tool_calls": [{"name": "lookup_booking", "arguments": {"ref": "RB-1"}}]}
    ai, text = await _ask([call] * 5 + ["Here's what I found."], [])
    assert text == "Here's what I found."
    assert ai.requests[-1]["tools"] is None          # the last call may not use tools
    assert len(ai.requests) == 6