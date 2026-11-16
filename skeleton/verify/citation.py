"""Citation verification: eight ordered checks against a snapshot (design 6.2).

Never raises. Every check is an explicit branch; there is no exception handling.
"""

import re
from dataclasses import dataclass

from skeleton.verify.codes import ReasonCode, render_message
from skeleton.verify.models import Citation, SnapshotView
from skeleton.verify.textnorm import normalise_quote, normalised_lines, split_lines

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SURROGATE = re.compile("[\ud800-\udfff]")


@dataclass(frozen=True)
class CitationOk:
    citation: Citation


@dataclass(frozen=True)
class Rejection:
    code: ReasonCode
    message: str


def _reject(code: ReasonCode, value: str = "") -> Rejection:
    return Rejection(code, render_message(code, value))


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_utf8(data: bytes) -> bool:
    # Lossy decode then re-encode round-trips only when the input was valid UTF-8.
    return data.decode("utf-8", errors="replace").encode("utf-8") == data


def verify_citation(view: SnapshotView, raw: object) -> CitationOk | Rejection:
    # 1. malformed
    if not isinstance(raw, dict):
        return _reject(ReasonCode.MALFORMED)
    file = raw.get("file")
    start = raw.get("line_start")
    end = raw.get("line_end")
    quote = raw.get("quote")
    if not isinstance(file, str) or not _is_int(start) or not _is_int(end):
        return _reject(ReasonCode.MALFORMED)
    if quote is not None and not isinstance(quote, str):
        return _reject(ReasonCode.MALFORMED)

    # 2. path_unsafe (lexical). Lone surrogates cannot be encoded for the
    # filesystem, so they are rejected here as well.
    if (
        file == ""
        or "\x00" in file
        or "\\" in file
        or file.startswith("/")
        or _DRIVE_PREFIX.match(file)
        or ".." in file.split("/")
        or _SURROGATE.search(file)
    ):
        return _reject(ReasonCode.PATH_UNSAFE, file)

    # 3. symlink (before file_not_found, design D1)
    if view.has_symlink_ancestor(file) or view.entry_kind(file) == "symlink":
        return _reject(ReasonCode.SYMLINK, file)

    # 4. file_not_found
    if view.entry_kind(file) is None:
        return _reject(ReasonCode.FILE_NOT_FOUND, file)
    data = view.read_bytes(file)
    if data is None:
        return _reject(ReasonCode.FILE_NOT_FOUND, file)

    span = f"{start}-{end}"

    # 5. range_invalid
    if start < 1 or start > end:
        return _reject(ReasonCode.RANGE_INVALID, span)

    # 6. range_out_of_bounds
    if end > len(split_lines(data)):
        return _reject(ReasonCode.RANGE_OUT_OF_BOUNDS, span)

    if quote is not None:
        # 7. file_unreadable
        if not _is_valid_utf8(data):
            return _reject(ReasonCode.FILE_UNREADABLE, file)

        # 8. quote_mismatch. A quote with lone surrogates cannot equal decoded
        # file text, and cannot be encoded by normalise_quote.
        if _SURROGATE.search(quote):
            return _reject(ReasonCode.QUOTE_MISMATCH, file)
        if normalise_quote(quote) != normalised_lines(data)[start - 1 : end]:
            return _reject(ReasonCode.QUOTE_MISMATCH, file)

    return CitationOk(Citation(file=file, line_start=start, line_end=end, quote=quote))
