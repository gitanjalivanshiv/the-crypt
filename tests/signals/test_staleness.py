from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
from skeleton.signals.staleness import Staleness, staleness_severity

CFG = SignalsConfig()
SRC = "import os\n\n\ndef f():\n    return 1\n"
PINNED = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


def make_snapshot(
    tmp_path: Path,
    days: int | None,
    text: str = SRC,
    history_available: bool = True,
) -> Snapshot:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "a.py").write_bytes(text.encode())
    history = (
        None
        if days is None
        else FileHistory(
            commit_count=4,
            last_modified=PINNED - timedelta(days=days),
            author_count=2,
        )
    )
    entry = FileEntry(
        path="a.py",
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
        pinned_commit_time=PINNED,
    )
    return Snapshot(tmp_path, meta, CodeGraph(files=[entry], symbols={}, imports={}))


@pytest.mark.parametrize(("days", "emitted"), [(364, 0), (365, 1), (366, 1)])
def test_threshold_boundary(tmp_path: Path, days: int, emitted: int) -> None:
    out = Staleness().analyze(make_snapshot(tmp_path, days), CFG)
    assert len(out.findings) == emitted


def test_metrics_and_severity(tmp_path: Path) -> None:
    f = Staleness().analyze(make_snapshot(tmp_path, 730), CFG).findings[0]
    assert f.analyzer == "staleness"
    assert f.metrics == {"days_since_modified": 730, "commit_count": 4}
    assert f.severity == pytest.approx(730 / 3650)
    assert (f.line_start, f.line_end) == (4, 5)


def test_future_last_modified_floors_at_zero(tmp_path: Path) -> None:
    assert Staleness().analyze(make_snapshot(tmp_path, -50), CFG).findings == []


def test_empty_file_and_no_history_produce_nothing(tmp_path: Path) -> None:
    assert Staleness().analyze(make_snapshot(tmp_path, 900, text=""), CFG).findings == []
    assert Staleness().analyze(make_snapshot(tmp_path, None), CFG).findings == []


@given(st.integers(0, 20000), st.integers(0, 20000))
def test_severity_monotone_and_bounded(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    assert 0.0 <= staleness_severity(lo, 3650) <= staleness_severity(hi, 3650) <= 1.0


def test_result_independent_of_system_clock(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path, 400)
    before = Staleness().analyze(snap, CFG)
    fake = datetime(2099, 1, 1, tzinfo=UTC)
    with patch("skeleton.signals.staleness.datetime", create=True) as m:
        m.now.return_value = fake
        m.utcnow.return_value = fake
        after = Staleness().analyze(snap, CFG)
    assert before == after


def test_registered_and_needs_history() -> None:
    assert any(isinstance(a, Staleness) for a in ANALYZERS)
    assert Staleness.needs_history is True


def test_run_all_skips_without_history(tmp_path: Path) -> None:
    snap = make_snapshot(tmp_path, None, history_available=False)
    result = run_all(snap, CFG, [Staleness()])
    assert result.findings == []
    assert result.analyzers[0].state == "skipped"
    assert result.analyzers[0].reason == "history_unavailable"


def test_run_all_passes_finding_gate(tmp_path: Path) -> None:
    result = run_all(make_snapshot(tmp_path, 500), CFG, [Staleness()])
    assert result.analyzers[0].state == "ok"
    assert len(result.findings) == 1
