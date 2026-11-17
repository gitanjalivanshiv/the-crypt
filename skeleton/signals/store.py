"""Findings persistence and the analysed snapshot (SnapshotView implementation).

Lives in signals, not ingest: ingest must not import signals (layering).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from skeleton.ingest.snapshot import Snapshot
from skeleton.signals import run_all
from skeleton.signals.models import FindingSet, SignalsConfig, finding_id

FINDINGS_FILE = "findings.json"


def load_findings(directory: str | Path) -> FindingSet:
    path = Path(directory) / FINDINGS_FILE
    return FindingSet.model_validate_json(path.read_text("utf-8"))


def analyse(snapshot_dir: str | Path, cfg: SignalsConfig | None = None) -> FindingSet:
    """Run all analyzers on the snapshot and write findings.json beside meta.json."""
    root = Path(snapshot_dir)
    result = run_all(Snapshot.open(root), cfg or SignalsConfig())
    (root / FINDINGS_FILE).write_text(result.model_dump_json(), encoding="utf-8")
    return result


class AnalysedSnapshot:
    """An ingest.Snapshot plus its FindingSet; satisfies verify.SnapshotView."""

    def __init__(self, snapshot: Snapshot, findings: FindingSet) -> None:
        self.snapshot = snapshot
        self.findings = findings
        self._by_id = {finding_id(f): f for f in findings.findings}

    @classmethod
    def open(cls, directory: str | Path) -> "AnalysedSnapshot":
        return cls(Snapshot.open(directory), load_findings(directory))

    @property
    def snapshot_id(self) -> str:
        return self.snapshot.meta.snapshot_id

    def entry_kind(self, path: str) -> Literal["file", "symlink"] | None:
        return self.snapshot.entry_kind(path)

    def has_symlink_ancestor(self, path: str) -> bool:
        return self.snapshot.has_symlink_ancestor(path)

    def read_bytes(self, path: str) -> bytes | None:
        return self.snapshot.read_bytes(path)

    def finding(self, finding_id: str) -> tuple[str, Mapping[str, int | float]] | None:
        f = self._by_id.get(finding_id)
        return None if f is None else (f.file, f.metrics)
