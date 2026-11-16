"""Line splitting and normalisation shared by the verifier for files and quotes."""

import re

_TERMINATOR = re.compile(rb"\r\n|\r|\n")


def split_lines(data: bytes) -> list[bytes]:
    """Split on CRLF, CR or LF. A single trailing terminator adds no line."""
    parts = _TERMINATOR.split(data)
    if parts[-1] == b"":
        parts.pop()
    return parts


def normalise_line(line: str) -> str:
    """Strip trailing space, tab, form feed and vertical tab only."""
    return line.rstrip(" \t\f\v")


def normalised_lines(data: bytes) -> list[str]:
    """Strictly decode UTF-8, split, and normalise each line."""
    text = data.decode("utf-8", errors="strict")
    return [normalise_line(p.decode("utf-8")) for p in split_lines(text.encode("utf-8"))]


def normalise_quote(text: str) -> list[str]:
    """Apply the same split and normalisation to a quote as to a file."""
    return [normalise_line(p.decode("utf-8")) for p in split_lines(text.encode("utf-8"))]
