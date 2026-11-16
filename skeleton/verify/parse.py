"""Parse raw model output into a list of raw claim items."""

import json
from typing import Any

_FENCE = "```"


class ParseFailure:
    """Returned when the text is not an object with a non-empty `claims` list."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def __repr__(self) -> str:
        return f"ParseFailure({self.reason!r})"


def _strip_fence(text: str) -> str:
    s = text.strip()
    if s.startswith(_FENCE) and s.endswith(_FENCE) and len(s) >= 2 * len(_FENCE):
        body = s[len(_FENCE) : -len(_FENCE)]
        # Drop the optional language tag on the opening fence line.
        first, sep, rest = body.partition("\n")
        s = rest if sep and " " not in first.strip() and "{" not in first else body
    return s.strip()


def parse_answer(text: str) -> list[Any] | ParseFailure:
    """Return the raw `claims` items, or a ParseFailure. Never raises."""
    try:
        data = json.loads(_strip_fence(text))
    except (ValueError, TypeError, RecursionError):
        return ParseFailure("not valid JSON")
    if not isinstance(data, dict):
        return ParseFailure("top level is not an object")
    claims = data.get("claims")
    if not isinstance(claims, list):
        return ParseFailure("`claims` is not a list")
    if not claims:
        return ParseFailure("`claims` is empty")
    return claims
