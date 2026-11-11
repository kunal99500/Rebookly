"""Seeing what the AI does: Langfuse traces (prompts, latency, tokens, cost) and our own ai_usage table.

Both are best-effort: if Langfuse or the usage table is unavailable, the AI feature still works.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("rebookly.ai")


@dataclass
class CallRecord:
    """Everything we know about one call to the AI provider. Never contains phone numbers or payment details."""
    feature: str
    model: str
    tier: str
    actor_type: str
    business_id: object | None
    attempt: int
    started: float = field(default_factory=time.perf_counter)
    input_tokens: int = 0
    output_tokens: int = 0
    success: bool = False
    error_type: str | None = None

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


class Tracer(Protocol):
    def start(self, record: CallRecord, messages: list[dict]) -> Any: ...
    def finish(self, handle: Any, record: CallRecord, output: str | None) -> None: ...


class NullTracer:
    def start(self, record: CallRecord, messages: list[dict]) -> None:
        return None

    def finish(self, handle: Any, record: CallRecord, output: str | None) -> None:
        return None


class LangfuseTracer:
    """Sends each call to Langfuse as a "generation". capture_content=False sends timings and tokens only."""

    def __init__(self, public_key: str, secret_key: str, base_url: str, capture_content: bool = True, environment: str | None = None):
        from langfuse import Langfuse  # imported here so the app runs even if Langfuse isn't installed

        self._client = Langfuse(public_key=public_key, secret_key=secret_key, base_url=base_url, environment=environment)
        self._capture = capture_content

    def start(self, record: CallRecord, messages: list[dict]) -> Any:
        try:
            return self._client.start_observation(
                name=record.feature, as_type="generation", model=record.model,
                input=messages if self._capture else None,
                metadata={"tier": record.tier, "attempt": record.attempt, "actor_type": record.actor_type,
                          "business_id": str(record.business_id) if record.business_id else None},
            )
        except Exception:
            logger.warning("Langfuse: could not start a trace", exc_info=True)
            return None

    def finish(self, handle: Any, record: CallRecord, output: str | None) -> None:
        if handle is None:
            return
        try:
            handle.update(
                output=output if self._capture else None,
                usage_details={"input": record.input_tokens, "output": record.output_tokens},
                level="DEFAULT" if record.success else "ERROR",
                status_message=record.error_type,
            )
            handle.end()
        except Exception:
            logger.warning("Langfuse: could not finish a trace", exc_info=True)

    def shutdown(self) -> None:
        try:
            self._client.shutdown()  # sends anything still queued
        except Exception:
            logger.warning("Langfuse: shutdown failed", exc_info=True)


class UsageRecorder(Protocol):
    async def __call__(self, record: CallRecord) -> None: ...


async def record_usage_in_database(record: CallRecord) -> None:
    """One ai_usage row per call: who, which feature, model, latency, tokens, success. No prompt text."""
    from app.db import is_db_ready, session_scope
    from app.models import AIUsage

    if not is_db_ready():
        return
    try:
        async with session_scope() as session:
            session.add(AIUsage(
                feature=record.feature, model=record.model, tier=record.tier, actor_type=record.actor_type,
                business_id=record.business_id, latency_ms=record.latency_ms, attempt=record.attempt,
                input_tokens=record.input_tokens, output_tokens=record.output_tokens,
                success=record.success, error_type=record.error_type,
            ))
            await session.commit()
    except Exception:
        logger.warning("Could not record AI usage", exc_info=True)