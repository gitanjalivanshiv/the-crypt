import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from skeleton.ingest.models import (
    CodeGraph,
    FileEntry,
    FileHistory,
    SnapshotMeta,
)
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals import ANALYZERS, SignalsConfig, run_all
from skeleton.signals.churn import Churn, churn_severity
from skeleton.verify.textnorm import normalised_lines

CFG = SignalsConfig()
SRC = "import os\n\n\ndef f():  \n    return 1\n"


def make_snapshot(
    tmp_path: Path,
    commits: int | None,
    text: str = SRC,
    history_available: bool = True,
    name: str = "a.py",
) -> Snapshot:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / name).write_bytes(text.encode())
    history = (
        None
        if commits is None
        else FileHistory(
            commit_count=commits,
            last_modified=datetime(2024, 1, 1, tzinfo=UTC),
            author_count=3,
        )
    )
    entry = FileEntry(
        path=name,
        size_bytes=len(text),
        line_count=len(text.splitlines()),
        is_symlink=False,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=history,
    )
    meta = SnapshotMeta(
        snapshot_id="snap",
        source="x",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=history_available,
        ingested_at=datetime.now(UTC),
        file_count=1,
        total_bytes=len(text),
        pinned_commit_time=datetime(2024, 6, 1, tzinfo=UTC),
    )
    return Snapshot(tmp_path, meta, CodeGraph(files=[entry], symbols={}, imports={}))


@pytest.mark.parametrize(("commits", "emitted"), [(9, 0), (10, 1), (11, 1)])
def test_threshold_boundary(tmp_path: Path, commits: int, emitted: int) -> None:
    out = Churn().analyze(make_snapshot(tmp_path, commits), CFG)
    assert len(out.findings) == emitted


def test_threshold_is_configurable(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path, 3)
    cfg = SignalsConfig(churn_min_commits=3)
    assert len(Churn().analyze(snap, cfg).findings) == 1


def test_metrics_and_evidence_match_normalised_slice(tmp_path: Path) -> None:
    f = Churn().analyze(make_snapshot(tmp_path, 12), CFG).findings[0]
    assert f.analyzer == "churn"
    assert f.metrics == {"commit_count": 12, "author_count": 3}
    lines = normalised_lines(SRC.encode())
    assert f.evidence == "\n".join(lines[f.line_start - 1 : f.line_end])
    assert (f.line_start, f.line_end) == (4, 5)
    assert "  " not in f.evidence.split("\n")[0][-2:]


def test_empty_file_produces_no_finding(tmp_path: Path) -> None:
    assert Churn().analyze(make_snapshot(tmp_path, 50, text=""), CFG).findings == []


def test_no_history_entry_produces_no_finding(tmp_path: Path) -> None:
    assert Churn().analyze(make_snapshot(tmp_path, None), CFG).findings == []


def test_non_python_file_uses_first_lines(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path, 20, text="a\nb\nc\nd\n", name="notes.txt")
    f = Churn().analyze(snap, CFG).findings[0]
    assert (f.line_start, f.line_end, f.evidence) == (1, 3, "a\nb\nc")


def test_severity_zero_at_one_commit() -> None:
    assert churn_severity(1, 200) == 0.0


def test_severity_saturates_at_200() -> None:
    assert churn_severity(200, 200) == pytest.approx(1.0)
    assert churn_severity(10_000, 200) == 1.0
    assert churn_severity(10, 200) == pytest.approx(math.log(10) / math.log(200))


@given(st.integers(1, 5000), st.integers(1, 5000))
def test_severity_monotone_and_bounded(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    assert 0.0 <= churn_severity(lo, 200) <= churn_severity(hi, 200) <= 1.0


def test_registered_and_needs_history() -> None:
    assert any(isinstance(a, Churn) for a in ANALYZERS)
    assert Churn.needs_history is True


def test_run_all_skips_without_history(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path, None, history_available=False)
    result = run_all(snap, CFG, [Churn()])
    assert result.findings == []
    assert result.analyzers[0].state == "skipped"
    assert result.analyzers[0].reason == "history_unavailable"


def test_run_all_passes_finding_gate(tmp_path: Path) -> None:
    result = run_all(make_snapshot(tmp_path, 15), CFG, [Churn()])
    assert result.analyzers[0].state == "ok"
    assert len(result.findings) == 1
