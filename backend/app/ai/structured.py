"""Turning the model's reply into a validated object. Pure functions, easy to test."""
import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class OutputError(ValueError):
    """The model's reply wasn't valid JSON for the expected shape."""


def extract_json(text: str) -> dict:
    """Accept a plain JSON object, or one wrapped in ```json fences."""
    cleaned = (text or "").strip()
    fenced = _FENCE.match(cleaned)
    if fenced:
        cleaned = fenced.group(1)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise OutputError(f"Not valid JSON: {err.msg}")
    if not isinstance(value, dict):
        raise OutputError("Expected a JSON object")
    return value


def parse_output(text: str, schema: type[T]) -> T:
    try:
        return schema.model_validate(extract_json(text))
    except ValidationError as err:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'value'}: {e['msg']}" for e in err.errors()[:8])
        raise OutputError(f"Doesn't match the expected shape: {problems}")


def schema_instructions(schema: type[BaseModel]) -> str:
    """Added to the system prompt so the model knows exactly which JSON to return."""
    return (
        "Reply with a single JSON object only, no other text. "
        f"It must match this JSON schema:\n{json.dumps(schema.model_json_schema(), separators=(',', ':'))}"
    )