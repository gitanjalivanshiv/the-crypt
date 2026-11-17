from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals import AnalyzerOutput, Finding, SignalsConfig, finding_id, run_all

CFG = SignalsConfig()
TEXT = "alpha  \nbeta\ngamma\n"


def make_snapshot(tmp_path: Path, history: bool) -> Snapshot:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text(TEXT)
    entry = FileEntry(
        path="a.py",
        size_bytes=len(TEXT),
        line_count=3,
        is_symlink=False,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=None,
    )
    meta = SnapshotMeta(
        snapshot_id="snap",
        source="x",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=history,
        ingested_at=datetime.now(UTC),
        file_count=1,
        total_bytes=len(TEXT),
        pinned_commit_time=None,
    )
    return Snapshot(tmp_path, meta, CodeGraph(files=[entry], symbols={}, imports={}))


def finding(
    analyzer: str,
    start: int = 1,
    end: int = 1,
    evidence: str = "alpha",
    file: str = "a.py",
) -> Finding:
    return Finding(
        analyzer=analyzer,
        file=file,
        line_start=start,
        line_end=end,
        evidence=evidence,
        severity=0.5,
        metrics={"n": 1},
    )


class Stub:
    needs_history: ClassVar[bool] = False
    requires: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        name: str,
        findings: list[Finding] | None = None,
        boom: bool = False,
        needs_history: bool = False,
        requires: frozenset[str] = frozenset(),
    ) -> None:
        self.name = name
        self._findings = findings or []
        self._boom = boom
        self.needs_history = needs_history
        self.requires = requires

    def analyze(self, snapshot: Snapshot, cfg: SignalsConfig) -> AnalyzerOutput:
        if self._boom:
            raise RuntimeError("kaboom")
        return AnalyzerOutput(self._findings)


def test_finding_id_and_validators() -> None:
    assert finding_id(finding("x", 1, 2, "alpha\nbeta")) == "x:a.py:1-2"
    base = {
        "analyzer": "x",
        "file": "a",
        "line_start": 1,
        "line_end": 1,
        "evidence": "e",
        "severity": 0.5,
        "metrics": {},
    }
    for bad in (
        {"severity": 1.5},
        {"severity": float("nan")},
        {"metrics": {"m": True}},
        {"metrics": {"m": float("inf")}},
        {"line_start": 3, "line_end": 2},
        {"extra": 1},
    ):
        with pytest.raises(ValidationError):
            Finding(**{**base, **bad})


def test_history_analyzer_skipped_without_history(tmp_path: Path) -> None:
    fs = run_all(make_snapshot(tmp_path, False), CFG, [Stub("h", needs_history=True)])
    assert fs.analyzers[0].state == "skipped"
    assert fs.analyzers[0].reason == "history_unavailable"


def test_missing_required_input_skipped(tmp_path: Path) -> None:
    a = Stub("d", requires=frozenset({"release_index"}))
    fs = run_all(make_snapshot(tmp_path, True), CFG, [a])
    assert fs.analyzers[0].reason == "release_index_unavailable"


def test_raising_analyzer_fails_and_others_run(tmp_path: Path) -> None:
    fs = run_all(
        make_snapshot(tmp_path, True),
        CFG,
        [Stub("bad", boom=True), Stub("good", [finding("good")])],
    )
    assert (fs.analyzers[0].state, fs.analyzers[0].reason) == ("failed", "kaboom")
    assert fs.analyzers[1].state == "ok"
    assert len(fs.findings) == 1


@pytest.mark.parametrize(
    "bad",
    [
        finding("a", file="missing.py"),
        finding("a", 1, 4, "x"),
        finding("a", evidence="wrong"),
        finding("a", evidence="alpha  "),
    ],
)
def test_invalid_finding_fails_whole_analyzer(tmp_path: Path, bad: Finding) -> None:
    fs = run_all(
        make_snapshot(tmp_path, True),
        CFG,
        [Stub("a", [finding("a", 2, 2, "beta"), bad])],
    )
    assert fs.analyzers[0].state == "failed"
    assert fs.analyzers[0].reason == f"invalid_finding: {finding_id(bad)}"
    assert fs.findings == []


def test_output_sorted_and_stable(tmp_path: Path) -> None:
    items = [
        finding("b", 2, 2, "beta"),
        finding("a", 3, 3, "gamma"),
        finding("a", 1, 2, "alpha\nbeta"),
        finding("a", 1, 1, "alpha"),
    ]
    snap = make_snapshot(tmp_path, True)
    first = run_all(snap, CFG, [Stub("b", items[:1]), Stub("a", items[1:])])
    second = run_all(snap, CFG, [Stub("a", items[1:]), Stub("b", items[:1])])
    assert [finding_id(f) for f in first.findings] == [
        "a:a.py:1-1",
        "a:a.py:1-2",
        "a:a.py:3-3",
        "b:a.py:2-2",
    ]
    assert first.findings == second.findings
