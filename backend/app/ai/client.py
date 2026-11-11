"""The one place Rebookly talks to the AI provider (OpenAI).

Features call complete_json(), complete_text() or run_with_tools(); this module adds the shared behaviour:
  * two model tiers: "fast" (cheap, simple tasks) and "smart" (judgement-heavy tasks),
  * JSON replies validated against a Pydantic schema, with one automatic retry if invalid,
  * tools the AI may ask for, run by our own permission-checked code,
  * a timeout, and clear errors so features can fall back gracefully,
  * tracing to Langfuse and a row in ai_usage for every call,
  * store=False, so OpenAI doesn't keep the conversation for its own use.

The AI never moves money and never sees phone numbers, payment IDs or card details:
features only send it what the task needs.
"""
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.observability import CallRecord, NullTracer, Tracer, UsageRecorder
from app.ai.structured import OutputError, parse_output, schema_instructions

logger = logging.getLogger("rebookly.ai")
T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "smart"]


class AIUnavailable(RuntimeError):
    """The AI provider couldn't be reached or refused the request. Features should fall back, not crash."""


class AIOutputError(RuntimeError):
    """The AI kept replying in the wrong shape. Features should fall back, not crash."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str          # JSON text, exactly as the model sent it


@dataclass(frozen=True)
class RawReply:
    text: str
    input_tokens: int
    output_tokens: int
    tool_calls: tuple[ToolCall, ...] = ()


class ToolError(Exception):
    """A tool couldn't do what was asked. The message is shown to the AI (and may reach the user)."""


@dataclass(frozen=True)
class Tool:
    """Something the AI may ask our code to do. Our code checks permissions; the AI only asks."""
    name: str
    description: str
    parameters: type[BaseModel]                         # validated before the tool runs
    run: Callable[[BaseModel], Awaitable[dict]]

    def spec(self) -> dict:
        schema = self.parameters.model_json_schema()
        schema.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": schema}}


class AIClient:
    def __init__(
        self, *, api_key: str, model_smart: str, model_fast: str, timeout_seconds: float = 30,
        tracer: Tracer | None = None, record_usage: UsageRecorder | None = None, json_retries: int = 1,
        max_output_tokens: int = 2000,
    ):
        if not api_key or not model_smart:
            raise ValueError("LLM_API_KEY and LLM_MODEL are required")
        from openai import AsyncOpenAI  # imported here so tests can run without network access

        self._openai = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=2)
        self._models = {"smart": model_smart, "fast": model_fast or model_smart}
        self._tracer = tracer or NullTracer()
        self._record_usage = record_usage
        self._json_retries = json_retries
        self._max_output_tokens = max_output_tokens

    async def close(self) -> None:
        await self._openai.close()
        shutdown = getattr(self._tracer, "shutdown", None)
        if shutdown:
            shutdown()

    # ---------- the only method that calls OpenAI (replaced by a fake in tests) ----------

    async def _call(self, model: str, messages: list[dict], json_mode: bool, tools: list[dict] | None = None) -> RawReply:
        import openai

        try:
            response = await self._openai.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else openai.NOT_GIVEN,
                tools=tools or openai.NOT_GIVEN,
                max_completion_tokens=self._max_output_tokens,
                store=False,
            )
        except openai.APIError as err:
            raise AIUnavailable(f"{type(err).__name__}: {getattr(err, 'message', err)}") from err
        usage = response.usage
        message = response.choices[0].message
        calls = tuple(
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
            for c in (message.tool_calls or []) if getattr(c, "function", None) is not None
        )
        return RawReply(
            text=message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            tool_calls=calls,
        )

    # ---------- shared plumbing ----------

    async def _traced_call(self, record: CallRecord, messages: list[dict], json_mode: bool,
                           tools: list[dict] | None = None) -> RawReply:
        handle = self._tracer.start(record, messages)
        reply = None
        try:
            reply = await self._call(record.model, messages, json_mode, tools)
            record.input_tokens, record.output_tokens = reply.input_tokens, reply.output_tokens
            record.success = True
            return reply
        except AIUnavailable:
            record.error_type = "provider_unavailable"
            raise
        except Exception as err:  # anything unexpected is treated as the provider being unavailable
            record.error_type = type(err).__name__
            raise AIUnavailable(str(err)) from err
        finally:
            output = None
            if reply is not None:
                output = reply.text or json.dumps([{"tool": c.name, "arguments": c.arguments} for c in reply.tool_calls])
            self._tracer.finish(handle, record, output)
            if self._record_usage:
                await self._record_usage(record)

    def _record(self, feature: str, tier: Tier, actor_type: str, business_id, attempt: int) -> CallRecord:
        return CallRecord(feature=feature, model=self._models[tier], tier=tier, actor_type=actor_type,
                          business_id=business_id, attempt=attempt)

    # ---------- what features use ----------

    async def complete_json(
        self, *, feature: str, system: str, user: str, schema: type[T], tier: Tier = "smart",
        actor_type: str = "system", business_id=None,
    ) -> T:
        """Ask for a JSON reply and return it as a validated `schema` object."""
        messages = [
            {"role": "system", "content": f"{system}\n\n{schema_instructions(schema)}"},
            {"role": "user", "content": user},
        ]
        for attempt in range(1, self._json_retries + 2):
            record = self._record(feature, tier, actor_type, business_id, attempt)
            reply = await self._traced_call(record, messages, json_mode=True)
            try:
                return parse_output(reply.text, schema)
            except OutputError as err:
                logger.info("AI reply for %s didn't match the schema (attempt %s): %s", feature, attempt, err)
                messages = messages + [
                    {"role": "assistant", "content": reply.text},
                    {"role": "user", "content": f"That reply was invalid. {err}. Reply again with corrected JSON only."},
                ]
        raise AIOutputError(f"The AI couldn't produce a valid reply for {feature}")

    async def complete_text(
        self, *, feature: str, system: str, user: str, tier: Tier = "fast",
        actor_type: str = "system", business_id=None,
    ) -> str:
        """Ask for a plain-text reply (e.g. a friendly explanation)."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        record = self._record(feature, tier, actor_type, business_id, 1)
        reply = await self._traced_call(record, messages, json_mode=False)
        return reply.text.strip()

    async def run_with_tools(
        self, *, feature: str, system: str, messages: list[dict], tools: list[Tool], tier: Tier = "smart",
        actor_type: str = "system", business_id=None, max_steps: int = 5,
    ) -> str:
        """A conversation turn where the AI may call our tools (look things up) before answering.

        Each tool's arguments are validated, and the tool itself checks permissions. Tool errors are
        returned to the AI as data, so it can explain them. After max_steps the AI must answer.
        """
        conversation = [{"role": "system", "content": system}, *messages]
        by_name = {tool.name: tool for tool in tools}
        specs = [tool.spec() for tool in tools]
        for step in range(1, max_steps + 1):
            record = self._record(feature, tier, actor_type, business_id, step)
            reply = await self._traced_call(record, conversation, json_mode=False, tools=specs)
            if not reply.tool_calls:
                return reply.text.strip()
            conversation.append({
                "role": "assistant", "content": reply.text or None,
                "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                               for c in reply.tool_calls],
            })
            for call in reply.tool_calls:
                result = await self._run_tool(by_name, call)
                conversation.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(result, default=str)})
        # Too many steps: ask for an answer with what we have, without more tools.
        record = self._record(feature, tier, actor_type, business_id, max_steps + 1)
        conversation.append({"role": "system", "content": "Answer the client now, without using any more tools."})
        reply = await self._traced_call(record, conversation, json_mode=False)
        return reply.text.strip()

    @staticmethod
    async def _run_tool(by_name: dict[str, Tool], call: ToolCall) -> dict:
        tool = by_name.get(call.name)
        if tool is None:
            return {"error": f"There is no tool called {call.name}"}
        try:
            args = tool.parameters.model_validate_json(call.arguments or "{}")
        except ValidationError as err:
            return {"error": "Invalid arguments: " + "; ".join(e["msg"] for e in err.errors()[:3])}
        try:
            return await tool.run(args)
        except ToolError as err:
            return {"error": str(err)}
        except Exception as err:  # e.g. a service raising HTTPException with a readable detail
            detail = getattr(err, "detail", None)
            if isinstance(detail, str):
                return {"error": detail}
            logger.exception("Tool %s failed", call.name)
            return {"error": "That didn't work. Please try again or contact the business."}