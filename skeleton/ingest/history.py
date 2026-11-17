"""Git history collector (D9): one `git log --no-renames` pass."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from skeleton.ingest.models import FileHistory

_TIMEOUT_S = 120


class HistoryResult(BaseModel):
    """`available=False` means no usable history; never zero-filled."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    files: dict[str, FileHistory] = {}
    pinned_commit_time: datetime | None = None


UNAVAILABLE = HistoryResult(available=False)


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return env


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        cwd=repo,
        env=_env(),
        capture_output=True,
        check=True,
        timeout=_TIMEOUT_S,
    )
    return result.stdout


def _ts(value: bytes) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)


def collect_history(repo: Path, sha: str) -> HistoryResult:
    """Return per-path history for the tree at `sha`, or UNAVAILABLE."""
    repo = Path(repo)
    try:
        if _git(repo, "rev-parse", "--is-shallow-repository").strip() == b"true":
            return UNAVAILABLE
        pinned = _ts(_git(repo, "show", "-s", "--format=%ct", sha).strip())
        tree = {
            p.decode("utf-8", "surrogateescape")
            for p in _git(repo, "ls-tree", "-r", "-z", "--name-only", sha).split(b"\0")
            if p
        }
        log = _git(
            repo, "log", "--topo-order", "--no-renames", "--name-only", "-z",
            "--format=%x01%H%x00%ct%x00%ae", sha,
        )
    except (subprocess.SubprocessError, OSError, ValueError):
        return UNAVAILABLE

    counts: dict[str, int] = {}
    authors: dict[str, set[str]] = {}
    last: dict[str, datetime] = {}
    try:
        for chunk in log.split(b"\x01"):
            if not chunk:
                continue
            parts = chunk.split(b"\0")
            if len(parts) < 3:
                continue
            when = _ts(parts[1])
            email = parts[2].decode("utf-8", "replace").strip().lower()
            seen: set[str] = set()
            for raw in parts[3:]:
                path = raw.lstrip(b"\n").decode("utf-8", "surrogateescape")
                if not path or path in seen:
                    continue
                seen.add(path)
                counts[path] = counts.get(path, 0) + 1
                authors.setdefault(path, set()).add(email)
                last.setdefault(path, when)
    except ValueError:
        return UNAVAILABLE

    files = {
        p: FileHistory(commit_count=counts[p], last_modified=last[p],
                       author_count=len(authors[p]))
        for p in counts
        if p in tree
    }
    if not files and not tree:
        return UNAVAILABLE
    return HistoryResult(available=True, files=files, pinned_commit_time=pinned)
