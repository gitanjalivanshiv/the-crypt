"""Finding anchor selection: pick the line range a file-level finding points at."""

from skeleton.ingest.parse import ParseResult
from skeleton.verify.textnorm import split_lines

_MAX_LINES = 3


def anchor_range(data: bytes, parse_result: ParseResult) -> tuple[int, int] | None:
    """Return 1-based inclusive (start, end), or None for a file with 0 lines.

    Preference: module docstring; first class/function definition capped at
    its first 3 lines; first min(3, line_count) lines.
    """
    line_count = len(split_lines(data))
    if line_count == 0:
        return None
    if parse_result.docstring_range is not None:
        return parse_result.docstring_range
    definitions = [s for s in parse_result.symbols if s.kind in ("class", "function")]
    if definitions:
        first = min(definitions, key=lambda s: s.line_start)
        return first.line_start, min(first.line_end, first.line_start + _MAX_LINES - 1)
    return 1, min(_MAX_LINES, line_count)
