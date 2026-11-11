"""Prompts live as Markdown files in app/ai/prompts/, so they can be improved without changing code.

Placeholders use $name (not {name}), so JSON examples inside prompts don't need escaping.
"""
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache
def _load(name: str) -> Template:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"No prompt named '{name}' in {PROMPTS_DIR}")
    return Template(path.read_text(encoding="utf-8"))


def render(name: str, **values: object) -> str:
    """Fill in a prompt. A missing value raises an error instead of sending a half-written prompt."""
    try:
        return _load(name).substitute({k: str(v) for k, v in values.items()})
    except KeyError as err:
        raise ValueError(f"Prompt '{name}' needs a value for {err}") from None