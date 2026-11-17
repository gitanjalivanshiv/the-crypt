"""Licence detection and the retention gate."""

import re
from pathlib import Path

from skeleton.ingest.models import Intent, IngestCode, IngestError

PERMITTED = frozenset({"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0"})
UNKNOWN = "unknown"


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", text.lower()).strip()


def _find_file(root: Path) -> Path | None:
    candidates = sorted(
        (p for p in root.iterdir() if p.name.lower().startswith(("license", "copying"))),
        key=lambda p: p.name,
    )
    for p in candidates:
        if p.is_file():
            return p
    return None


def _identify(text: str) -> str:
    t = _normalise(text)
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0"
    if "permission is hereby granted free of charge" in t and "without restriction" in t:
        return "MIT"
    if (
        "redistribution and use in source and binary forms" in t
        and "this list of conditions" in t
    ):
        if "neither the name of" in t:
            return "BSD-3-Clause"
        return "BSD-2-Clause"
    return UNKNOWN


def detect_licence(root: Path) -> str:
    """Return the SPDX id of the root licence file, or `unknown`."""
    try:
        path = _find_file(Path(root))
        if path is None:
            return UNKNOWN
        return _identify(path.read_bytes().decode("utf-8", errors="replace"))
    except OSError:
        return UNKNOWN


def apply_gate(licence: str, intent: Intent) -> bool:
    """Return `retainable`; raise for retained snapshots with a non-permitted licence."""
    if intent == "ephemeral":
        return False
    if licence not in PERMITTED:
        raise IngestError(
            IngestCode.licence_not_permitted,
            f"licence {licence!r} is not permitted for retained snapshots",
        )
    return True
