"""A pretend AI for tests: returns scripted replies, records every request, never touches the network."""
import json

from app.ai.client import AIClient, AIUnavailable, RawReply, ToolCall


class FakeAI(AIClient):
    """Replies can be text, an exception to raise, or {"tool_calls": [{"name": ..., "arguments": {...}}]}."""

    def __init__(self, replies: list, **kwargs):
        self._openai = None
        self._models = {"smart": "fake-smart", "fast": "fake-fast"}
        from app.ai.observability import NullTracer

        self._tracer = kwargs.get("tracer") or NullTracer()
        self._record_usage = kwargs.get("record_usage")
        self._json_retries = kwargs.get("json_retries", 1)
        self._replies = list(replies)
        self.requests: list[dict] = []

    async def close(self) -> None:
        return None

    async def _call(self, model: str, messages: list[dict], json_mode: bool, tools: list[dict] | None = None) -> RawReply:
        self.requests.append({"model": model, "messages": list(messages), "json_mode": json_mode, "tools": tools})
        if not self._replies:
            raise AIUnavailable("FakeAI has no more scripted replies")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, dict):
            calls = tuple(ToolCall(id=f"call_{i}", name=c["name"], arguments=json.dumps(c.get("arguments", {})))
                          for i, c in enumerate(reply["tool_calls"]))
            return RawReply(text="", input_tokens=100, output_tokens=20, tool_calls=calls)
        return RawReply(text=reply, input_tokens=100, output_tokens=20)