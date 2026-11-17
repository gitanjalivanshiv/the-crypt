"""Retention and refs (design 10.3, D4, R1.15, R9.9).

Retained snapshots are addressed by Snapshot ID; ephemeral ones by an opaque random
ref so two users pasting the same repo never share a snapshot. Ephemeral snapshots
are deleted on ``DELETE``, when the TTL elapses, and on shutdown.
"""

import re
import secrets
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from skeleton.api.errors import ApiCode

Intent = Literal["retained", "ephemeral"]

_EPHEMERAL_REF_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class RetainedNotAllowed(Exception):
    """``retained`` was requested on a server with ``allow_retained = False``."""

    code = ApiCode.retained_not_allowed

    def __init__(self) -> None:
        super().__init__("this server does not allow retained snapshots")


def resolve_intent(intent: str | None, *, allow_retained: bool) -> Intent:
    """Default to ``ephemeral``; ``retained`` is refused unless the server allows it."""
    if intent is None or intent == "ephemeral":
        return "ephemeral"
    if intent == "retained":
        if not allow_retained:
            raise RetainedNotAllowed()
        return "retained"
    raise ValueError(f"unknown intent {intent!r}")


class Retention:
    """Tracks ephemeral snapshot directories under ``<store>/ephemeral/<ref>/``."""

    def __init__(
        self,
        store: Path,
        ttl_s: int = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = Path(store)
        self.ttl_s = ttl_s
        self._clock = clock
        self._created: dict[str, float] = {}
        # Directories already on disk start their TTL now.
        if self.root.is_dir():
            for child in self.root.iterdir():
                if child.is_dir():
                    self._created[child.name] = self._clock()

    @property
    def root(self) -> Path:
        return self.store / "ephemeral"

    def new_ephemeral_ref(self) -> str:
        """A fresh unguessable ref, registered with the current time."""
        ref = secrets.token_urlsafe(16)
        self._created[ref] = self._clock()
        return ref

    def ephemeral_dir(self, ref: str) -> Path:
        if not _EPHEMERAL_REF_RE.fullmatch(ref):
            raise ValueError(f"invalid ephemeral ref {ref!r}")
        return self.root / ref

    @staticmethod
    def retained_ref(snapshot_id: str) -> str:
        return snapshot_id

    def register(self, ref: str) -> None:
        self._created[ref] = self._clock()

    def delete(self, ref: str) -> bool:
        """Delete an ephemeral snapshot. False if there is none (retained refs never match)."""
        if not _EPHEMERAL_REF_RE.fullmatch(ref):
            return False
        directory = self.root / ref
        existed = directory.is_dir()
        self._created.pop(ref, None)
        if existed:
            shutil.rmtree(directory, ignore_errors=True)
        return existed

    def sweep(self) -> list[str]:
        """Delete every ephemeral snapshot older than the TTL; return the refs removed."""
        now = self._clock()
        expired = [r for r, t in self._created.items() if now - t >= self.ttl_s]
        for ref in expired:
            self.delete(ref)
        return expired

    def cleanup_all(self) -> None:
        """Shutdown cleanup: remove every ephemeral snapshot."""
        if self.root.is_dir():
            for child in self.root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
        self._created.clear()
