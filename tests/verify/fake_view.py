"""Test doubles for SnapshotView: an in-memory FakeView and a RealDirView on disk.

Both follow lstat semantics: entry_kind looks only at the final path component
(a file reached through a symlinked directory is still a "file"), and
has_symlink_ancestor reports whether any parent component is a symlink.
"""

import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

Metrics = Mapping[str, int | float]
Findings = Mapping[str, tuple[str, Metrics]]


class FakeView:
    def __init__(
        self,
        files: Mapping[str, bytes] | None = None,
        symlinks: Mapping[str, str] | None = None,
        symlink_dirs: Mapping[str, str] | None = None,
        findings: Findings | None = None,
        snapshot_id: str = "snap-fake",
    ) -> None:
        self.snapshot_id = snapshot_id
        self.files = dict(files or {})
        self.symlinks = dict(symlinks or {})  # link path -> target file path
        self.symlink_dirs = dict(symlink_dirs or {})  # link dir -> target dir
        self.findings = dict(findings or {})

    def _resolve_parents(self, path: str) -> str:
        parts = path.split("/")
        out: list[str] = []
        for part in parts[:-1]:
            out.append(part)
            joined = "/".join(out)
            if joined in self.symlink_dirs:
                out = self.symlink_dirs[joined].split("/")
        return "/".join([*out, parts[-1]])

    def entry_kind(self, path: str) -> Literal["file", "symlink"] | None:
        resolved = self._resolve_parents(path)
        if resolved in self.symlinks or resolved in self.symlink_dirs:
            return "symlink"
        if resolved in self.files:
            return "file"
        return None

    def has_symlink_ancestor(self, path: str) -> bool:
        parts = path.split("/")
        return any("/".join(parts[:i]) in self.symlink_dirs for i in range(1, len(parts)))

    def read_bytes(self, path: str) -> bytes | None:
        resolved = self._resolve_parents(path)
        if resolved in self.symlinks:
            resolved = self._resolve_parents(self.symlinks[resolved])
        return self.files.get(resolved)

    def finding(self, finding_id: str) -> tuple[str, Metrics] | None:
        return self.findings.get(finding_id)


class RealDirView:
    """Same protocol over a real directory, using lstat."""

    def __init__(
        self,
        root: Path,
        files: Mapping[str, bytes] | None = None,
        symlinks: Mapping[str, str] | None = None,
        symlink_dirs: Mapping[str, str] | None = None,
        findings: Findings | None = None,
        snapshot_id: str = "snap-fake",
    ) -> None:
        self.snapshot_id = snapshot_id
        self.root = Path(root)
        self.findings = dict(findings or {})
        for rel, data in (files or {}).items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for rel, dest in (symlinks or {}).items():
            link = self.root / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(self.root / dest, link)
        for rel, dest in (symlink_dirs or {}).items():
            link = self.root / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(self.root / dest, link, target_is_directory=True)

    def entry_kind(self, path: str) -> Literal["file", "symlink"] | None:
        try:
            mode = os.lstat(self.root / path).st_mode
        except OSError:
            return None
        if stat.S_ISLNK(mode):
            return "symlink"
        if stat.S_ISREG(mode):
            return "file"
        return None

    def has_symlink_ancestor(self, path: str) -> bool:
        parts = path.split("/")
        for i in range(1, len(parts)):
            try:
                mode = os.lstat(self.root.joinpath(*parts[:i])).st_mode
            except OSError:
                return False
            if stat.S_ISLNK(mode):
                return True
        return False

    def read_bytes(self, path: str) -> bytes | None:
        try:
            return (self.root / path).read_bytes()
        except OSError:
            return None

    def finding(self, finding_id: str) -> tuple[str, Metrics] | None:
        return self.findings.get(finding_id)
