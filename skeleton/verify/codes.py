"""Reason codes for rejected citations and claims, with fixed message templates."""

from enum import StrEnum
from typing import Final


class ReasonCode(StrEnum):
    MALFORMED = "malformed"
    PATH_UNSAFE = "path_unsafe"
    FILE_NOT_FOUND = "file_not_found"
    SYMLINK = "symlink"
    RANGE_INVALID = "range_invalid"
    RANGE_OUT_OF_BOUNDS = "range_out_of_bounds"
    FILE_UNREADABLE = "file_unreadable"
    QUOTE_MISMATCH = "quote_mismatch"
    UNCITED_CLAIM = "uncited_claim"
    FIGURE_NOT_IN_METRICS = "figure_not_in_metrics"
    FIGURE_NOT_CITED = "figure_not_cited"
    UNBACKED_NUMBER = "unbacked_number"


# Each template has at most one placeholder, ``{value}``: the failing path,
# number or token. Model prose is never interpolated.
MESSAGES: Final[dict[ReasonCode, str]] = {
    ReasonCode.MALFORMED: "The claim or citation is malformed.",
    ReasonCode.PATH_UNSAFE: "Unsafe path: {value}",
    ReasonCode.FILE_NOT_FOUND: "File not found: {value}",
    ReasonCode.SYMLINK: "Symlinked path not allowed: {value}",
    ReasonCode.RANGE_INVALID: "Invalid line range: {value}",
    ReasonCode.RANGE_OUT_OF_BOUNDS: "Line range is outside the file: {value}",
    ReasonCode.FILE_UNREADABLE: "File is not readable as UTF-8: {value}",
    ReasonCode.QUOTE_MISMATCH: "Quote does not match the cited lines: {value}",
    ReasonCode.UNCITED_CLAIM: "A factual claim needs at least one citation.",
    ReasonCode.FIGURE_NOT_IN_METRICS: "Figure does not match the metrics: {value}",
    ReasonCode.FIGURE_NOT_CITED: "Figure's file is not cited: {value}",
    ReasonCode.UNBACKED_NUMBER: "Number not backed by a verified source: {value}",
}


def render_message(code: ReasonCode, value: str = "") -> str:
    """Return the fixed message for ``code`` with only ``value`` interpolated."""
    return MESSAGES[code].format(value=value)
