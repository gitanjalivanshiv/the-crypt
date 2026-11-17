"""Snapshot ingest: URL orchestration (design section 4)."""

from __future__ import annotations

import os
import secrets
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from skeleton.ingest.clone import clone_and_pin
from skeleton.ingest.graph import build_graph
from skeleton.ingest.history import collect_history
from skeleton.ingest.licence import apply_gate, detect_licence
from skeleton.ingest.models import DEFAULT_INTENT, IngestLimits, Intent, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.ingest.source import Resolver, default_resolver, validate_url

__all__ = ["IngestLimits", "Snapshot", "ingest_archive", "ingest_url"]


def ingest_archive(*args, **kwargs) -> Snapshot:  # type: ignore[no-untyped-def]
    """Ingest a .zip / .tar.gz upload; see skeleton.ingest.archive."""
    from skeleton.ingest.archive import ingest_archive as _impl

    return _impl(*args, **kwargs)


def _make_tree_writable(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        for name in [*dirs, *files]:
            p = os.path.join(root, name)
            if not os.path.islink(p):
                os.chmod(p, os.lstat(p).st_mode | stat.S_IWUSR)
    if path.exists():
        os.chmod(path, os.lstat(path).st_mode | stat.S_IWUSR)


def _make_read_only(path: Path) -> None:
    for root, dirs, files in os.walk(path, topdown=False):
        for name in [*files, *dirs]:
            p = os.path.join(root, name)
            if not os.path.islink(p):
                os.chmod(p, os.lstat(p).st_mode & ~0o222)
    os.chmod(path, os.lstat(path).st_mode & ~0o222)


def _remove(path: Path) -> None:
    if path.exists():
        _make_tree_writable(path)
        shutil.rmtree(path, ignore_errors=True)


def ingest_url(
    url: str,
    *,
    ref: str | None = None,
    sha: str | None = None,
    intent: Intent = DEFAULT_INTENT,
    limits: IngestLimits | None = None,
    store: Path,
    resolver: Resolver = default_resolver,
    git_bin: str = "git",
    _allow_protocols: str = "https",
) -> Snapshot:
    """Ingest a git URL into `store` and return the opened Snapshot."""
    limits = limits or IngestLimits()
    store = Path(store)
    validate_url(url, resolver=resolver)

    store.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=store))
    try:
        repo = staging / "repo"
        pinned = clone_and_pin(
            url, ref=ref, sha=sha, limits=limits, dest=repo,
            git_bin=git_bin, _allow_protocols=_allow_protocols,
        )
        licence = detect_licence(repo)
        retainable = apply_gate(licence, intent)
        graph = build_graph(repo)
        hist = collect_history(repo, pinned)
        if hist.available:
            graph = graph.model_copy(
                update={
                    "files": [
                        f.model_copy(update={"history": hist.files.get(f.path)})
                        for f in graph.files
                    ]
                }
            )
        meta = SnapshotMeta(
            snapshot_id=pinned,
            source=url,
            licence=licence,
            retainable=retainable,
            intent=intent,
            history_available=hist.available,
            ingested_at=datetime.now(UTC),
            file_count=len(graph.files),
            total_bytes=sum(f.size_bytes for f in graph.files),
            pinned_commit_time=hist.pinned_commit_time,
        )
        (staging / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
        (staging / "graph.json").write_text(graph.model_dump_json(), encoding="utf-8")
        _make_read_only(repo)

        if intent == "retained":
            final = store / "retained" / pinned.replace(":", "-")
        else:
            final = store / "ephemeral" / secrets.token_urlsafe(16)
        final.parent.mkdir(parents=True, exist_ok=True)
        _remove(final)
        os.rename(staging, final)
        return Snapshot.open(final)
    except BaseException:
        _remove(staging)
        raise
