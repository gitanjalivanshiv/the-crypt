"""Read-only view of an ingested snapshot directory (file side of SnapshotView)."""

import os
import stat
from pathlib import Path
from typing import Literal

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta


class Snapshot:
    def __init__(self, root: Path, meta: SnapshotMeta, graph: CodeGraph) -> None:
        self.root = root
        self.meta = meta
        self.graph = graph
        self._index: dict[str, FileEntry] = {f.path: f for f in graph.files}

    @classmethod
    def open(cls, directory: str | Path) -> "Snapshot":
        root = Path(directory)
        meta = SnapshotMeta.model_validate_json((root / "meta.json").read_text("utf-8"))
        graph = CodeGraph.model_validate_json((root / "graph.json").read_text("utf-8"))
        return cls(root, meta, graph)

    @property
    def repo(self) -> Path:
        return self.root / "repo"

    def entry(self, path: str) -> FileEntry | None:
        return self._index.get(path)

    def entry_kind(self, path: str) -> Literal["file", "symlink"] | None:
        entry = self._index.get(path)
        if entry is None:
            return None
        return "symlink" if entry.is_symlink else "file"

    def has_symlink_ancestor(self, path: str) -> bool:
        parts = path.split("/")
        current = self.repo
        for part in parts[:-1]:
            current = current / part
            try:
                if stat.S_ISLNK(os.lstat(current).st_mode):
                    return True
            except OSError:
                return False
        return False

    def read_bytes(self, path: str) -> bytes | None:
        try:
            if self.entry_kind(path) != "file" or self.has_symlink_ancestor(path):
                return None
            return (self.repo / path).read_bytes()
        except (OSError, ValueError):  # unreadable or malformed path: contract is None, never raise
            return None
