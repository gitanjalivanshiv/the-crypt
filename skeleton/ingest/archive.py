"""Archive (.zip / .tar.gz) ingest (design section 4.1).

Members are extracted one at a time with exclusive-create. Declared sizes are
never trusted: the bytes actually written are counted against the limits.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from skeleton.ingest.graph import build_graph
from skeleton.ingest.history import collect_history
from skeleton.ingest.licence import apply_gate, detect_licence
from skeleton.ingest.models import (
    DEFAULT_INTENT,
    IngestCode,
    IngestError,
    IngestLimits,
    Intent,
    SnapshotMeta,
)
from skeleton.ingest.snapshot import Snapshot

_CHUNK = 64 * 1024
_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
_GZIP_MAGIC = b"\x1f\x8b"
_MAX_LINK_TARGET = 4096
_DRIVE = re.compile(r"^[A-Za-z]:")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _unsafe(detail: str) -> IngestError:
    return IngestError(IngestCode.unsafe_archive, detail)


def _too_big(limits: IngestLimits) -> IngestError:
    return IngestError(
        IngestCode.size_limit_exceeded, f"archive content exceeds {limits.max_bytes} bytes"
    )


def _parts(name: str) -> list[str]:
    """Normalise an archive member name; raise unsafe_archive if it escapes."""
    if "\0" in name or "\\" in name or name.startswith("/") or _DRIVE.match(name):
        raise _unsafe(f"unsafe member name: {name!r}")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise _unsafe(f"path traversal in member name: {name!r}")
    return parts


def _check_link_target(parts: list[str], target: str, name: str) -> None:
    """A symlink must resolve lexically inside the archive root."""
    if not target or "\0" in target or "\\" in target or target.startswith("/") or _DRIVE.match(target):
        raise _unsafe(f"symlink {name!r} has unsafe target {target!r}")
    depth = len(parts) - 1
    for seg in target.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            depth -= 1
            if depth < 0:
                raise _unsafe(f"symlink {name!r} points outside the archive: {target!r}")
        else:
            depth += 1


class _Extractor:
    def __init__(self, raw: Path, limits: IngestLimits) -> None:
        self.raw = raw
        self.limits = limits
        self.written = 0
        self.files = 0

    def _target(self, parts: list[str], *, make_parents: bool = True) -> Path:
        cur = self.raw
        for seg in parts[:-1]:
            cur = cur / seg
            if os.path.islink(cur):
                raise _unsafe(f"member path passes through a symlink: {'/'.join(parts)!r}")
            if make_parents:
                try:
                    cur.mkdir(exist_ok=True)
                except (FileExistsError, NotADirectoryError):
                    raise _unsafe(f"conflicting member path: {'/'.join(parts)!r}") from None
        return cur / parts[-1]

    def _count_file(self) -> None:
        self.files += 1
        if self.files > self.limits.max_files:
            raise IngestError(
                IngestCode.file_limit_exceeded,
                f"archive has more than {self.limits.max_files} entries",
            )

    def directory(self, parts: list[str]) -> None:
        if not parts:
            return
        dest = self._target(parts)
        try:
            dest.mkdir(exist_ok=True)
        except (FileExistsError, NotADirectoryError):
            raise _unsafe(f"conflicting directory entry: {'/'.join(parts)!r}") from None
        if os.path.islink(dest):
            raise _unsafe(f"directory entry replaces a symlink: {'/'.join(parts)!r}")

    def file(self, parts: list[str], reader: BinaryIO) -> None:
        if not parts:
            raise _unsafe("file member with empty name")
        self._count_file()
        dest = self._target(parts)
        try:
            out = open(dest, "xb")  # noqa: SIM115 - exclusive create, never overwrite
        except (FileExistsError, IsADirectoryError, NotADirectoryError):
            raise _unsafe(f"duplicate or conflicting member: {'/'.join(parts)!r}") from None
        with out:
            while True:
                chunk = reader.read(_CHUNK)
                if not chunk:
                    break
                self.written += len(chunk)
                if self.written > self.limits.max_bytes:
                    raise _too_big(self.limits)
                out.write(chunk)

    def symlink(self, parts: list[str], target: str, name: str) -> None:
        if not parts:
            raise _unsafe("symlink member with empty name")
        _check_link_target(parts, target, name)
        self._count_file()
        dest = self._target(parts)
        try:
            os.symlink(target, dest)
        except (FileExistsError, NotADirectoryError):
            raise _unsafe(f"duplicate or conflicting member: {name!r}") from None

    def hardlink(self, parts: list[str], target_name: str, name: str) -> None:
        tparts = _parts(target_name)
        if not tparts or not parts:
            raise _unsafe(f"hardlink {name!r} has an invalid target")
        src = self.raw.joinpath(*tparts)
        if os.path.islink(src) or not os.path.isfile(src):
            raise _unsafe(f"hardlink {name!r} target is not an extracted regular file")
        for i in range(1, len(tparts)):
            if os.path.islink(self.raw.joinpath(*tparts[:i])):
                raise _unsafe(f"hardlink {name!r} target passes through a symlink")
        with open(src, "rb") as fh:
            self.file(parts, fh)


def _extract_zip(path: Path, ex: _Extractor) -> None:
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            name = info.filename
            parts = _parts(name)
            mode = info.external_attr >> 16
            if name.endswith("/") or info.is_dir():
                ex.directory(parts)
            elif stat.S_ISLNK(mode):
                if info.file_size > _MAX_LINK_TARGET:
                    raise _unsafe(f"symlink {name!r} target too long")
                with zf.open(info) as fh:
                    target = fh.read(_MAX_LINK_TARGET + 1).decode("utf-8", "replace")
                ex.symlink(parts, target, name)
            elif stat.S_IFMT(mode) and not stat.S_ISREG(mode):
                raise _unsafe(f"unsupported member type: {name!r}")
            else:
                with zf.open(info) as fh:
                    ex.file(parts, fh)


def _extract_tar(path: Path, ex: _Extractor) -> None:
    with tarfile.open(path, mode="r|gz") as tf:
        for m in tf:
            parts = _parts(m.name)
            if m.isdir():
                ex.directory(parts)
            elif m.issym():
                ex.symlink(parts, m.linkname, m.name)
            elif m.islnk():
                ex.hardlink(parts, m.linkname, m.name)
            elif m.isreg():
                fh = tf.extractfile(m)
                if fh is None:
                    raise _unsafe(f"unreadable member: {m.name!r}")
                with fh:
                    ex.file(parts, fh)
            else:
                raise _unsafe(f"unsupported member type: {m.name!r}")


def _spool(data: bytes | BinaryIO, dest: Path, limits: IngestLimits) -> str:
    """Write the upload to `dest`, returning its SHA-256 hex digest."""
    digest = hashlib.sha256()
    total = 0

    def chunks() -> Iterator[bytes]:
        if isinstance(data, (bytes, bytearray, memoryview)):
            view = memoryview(data)
            for i in range(0, len(view), _CHUNK):
                yield bytes(view[i : i + _CHUNK])
        else:
            while True:
                c = data.read(_CHUNK)
                if not c:
                    return
                yield c

    with open(dest, "xb") as out:
        for chunk in chunks():
            total += len(chunk)
            if total > limits.max_bytes:
                raise _too_big(limits)
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def _sniff(path: Path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head.startswith(_ZIP_MAGIC):
        return "zip"
    if head.startswith(_GZIP_MAGIC):
        return "tar.gz"
    raise IngestError(
        IngestCode.invalid_source, "unsupported archive format (expected .zip or .tar.gz)"
    )


def _check_symlinks(root: Path) -> None:
    real_root = os.path.realpath(root)
    for cur, dirs, files in os.walk(root):
        for n in [*dirs, *files]:
            p = os.path.join(cur, n)
            if os.path.islink(p):
                real = os.path.realpath(p)
                if real != real_root and not real.startswith(real_root + os.sep):
                    raise _unsafe(f"symlink escapes the snapshot root: {os.path.relpath(p, root)!r}")


def _git_env() -> dict[str, str]:
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


def _embedded_head(repo: Path) -> str | None:
    """Resolve HEAD of an embedded `.git` to a SHA, neutralising its config and hooks."""
    git_dir = repo / ".git"
    if os.path.islink(git_dir) or not git_dir.is_dir():
        return None
    cfg = git_dir / "config"
    try:
        if os.path.islink(cfg):
            cfg.unlink()
        cfg.write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
        hooks = git_dir / "hooks"
        if os.path.islink(hooks):
            hooks.unlink()
        elif hooks.exists():
            shutil.rmtree(hooks)
        res = subprocess.run(
            ["git", "-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false",
             "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
            env=_git_env(), stdin=subprocess.DEVNULL, capture_output=True,
            check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = res.stdout.decode("utf-8", "replace").strip()
    return sha if res.returncode == 0 and _SHA.match(sha) else None


def ingest_archive(
    data: bytes | BinaryIO,
    *,
    filename: str,
    intent: Intent = DEFAULT_INTENT,
    limits: IngestLimits | None = None,
    store: Path,
) -> Snapshot:
    """Ingest a .zip or .tar.gz upload into `store` and return the opened Snapshot."""
    from skeleton.ingest import _make_read_only, _remove

    limits = limits or IngestLimits()
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=store))
    try:
        upload = staging / "upload.bin"
        digest = _spool(data, upload, limits)
        fmt = _sniff(upload)

        raw = staging / "raw"
        raw.mkdir()
        ex = _Extractor(raw, limits)
        try:
            if fmt == "zip":
                _extract_zip(upload, ex)
            else:
                _extract_tar(upload, ex)
        except IngestError:
            raise
        except (zipfile.BadZipFile, tarfile.TarError, EOFError, zlib.error,
                RuntimeError, NotImplementedError, OSError, UnicodeError) as exc:
            raise IngestError(IngestCode.invalid_source, f"corrupt archive: {exc}") from exc
        upload.unlink()

        entries = os.listdir(raw)
        repo = staging / "repo"
        if len(entries) == 1 and (raw / entries[0]).is_dir() and not os.path.islink(raw / entries[0]):
            os.rename(raw / entries[0], repo)
            raw.rmdir()
        else:
            os.rename(raw, repo)
        _check_symlinks(repo)

        head = _embedded_head(repo)
        hist = collect_history(repo, head) if head else None
        snapshot_id = head if head else f"sha256:{digest}"
        history_available = bool(hist and hist.available)

        licence = detect_licence(repo)
        retainable = apply_gate(licence, intent)
        graph = build_graph(repo)
        if history_available and hist is not None:
            graph = graph.model_copy(
                update={
                    "files": [
                        f.model_copy(update={"history": hist.files.get(f.path)})
                        for f in graph.files
                    ]
                }
            )
        else:
            graph = graph.model_copy(
                update={"files": [f.model_copy(update={"history": None}) for f in graph.files]}
            )
        meta = SnapshotMeta(
            snapshot_id=snapshot_id,
            source=f"archive:{os.path.basename(filename)}",
            licence=licence,
            retainable=retainable,
            intent=intent,
            history_available=history_available,
            ingested_at=datetime.now(UTC),
            file_count=len(graph.files),
            total_bytes=sum(f.size_bytes for f in graph.files),
            pinned_commit_time=hist.pinned_commit_time if history_available and hist else None,
        )
        (staging / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
        (staging / "graph.json").write_text(graph.model_dump_json(), encoding="utf-8")
        _make_read_only(repo)

        if intent == "retained":
            final = store / "retained" / snapshot_id.replace(":", "-")
        else:
            final = store / "ephemeral" / secrets.token_urlsafe(16)
        final.parent.mkdir(parents=True, exist_ok=True)
        _remove(final)
        os.rename(staging, final)
        return Snapshot.open(final)
    except BaseException:
        _remove(staging)
        raise
