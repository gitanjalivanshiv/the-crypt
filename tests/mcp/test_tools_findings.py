"""SignalTools get_snapshot and list_findings on an in-memory analysed snapshot."""

from datetime import UTC, datetime
from pathlib import Path

from skeleton.ingest.models import CodeGraph, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.contract import ErrorCode, ErrorResponse, ListFindingsOutput
from skeleton.mcp.tools import SignalTools
from skeleton.signals.models import AnalyzerStatus, Finding, FindingSet
from skeleton.signals.store import AnalysedSnapshot

SNAP_ID = "a" * 40


def _finding(analyzer: str, file: str, start: int, severity: float) -> Finding:
    return Finding(
        analyzer=analyzer,
        file=file,
        line_start=start,
        line_end=start,
        evidence="e",
        severity=severity,
        metrics={"commit_count": 1},
    )


def _tools(
    findings: list[Finding], analyzers: list[AnalyzerStatus] | None = None
) -> SignalTools:
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="https://example.com/r.git",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=3,
        total_bytes=10,
        pinned_commit_time=None,
    )
    snap = Snapshot(Path("."), meta, CodeGraph(files=[], symbols={}, imports={}))
    statuses = analyzers or [
        AnalyzerStatus(name="churn", state="ok", total_found=len(findings))
    ]
    return SignalTools(
        AnalysedSnapshot(
            snap, FindingSet(snapshot_id=SNAP_ID, findings=findings, analyzers=statuses)
        )
    )


def _ok(result: object) -> ListFindingsOutput:
    assert isinstance(result, ListFindingsOutput)
    return result


def test_get_snapshot() -> None:
    out = _tools([]).get_snapshot()
    assert (out.snapshot_id, out.licence, out.file_count) == (SNAP_ID, "MIT", 3)
    assert out.analyzers[0].name == "churn"


def test_ordering_severity_then_file_then_line() -> None:
    fs = [
        _finding("churn", "b.py", 1, 0.5),
        _finding("churn", "a.py", 9, 0.5),
        _finding("churn", "a.py", 2, 0.5),
        _finding("todo_age", "z.py", 1, 0.9),
    ]
    out = _ok(_tools(fs).list_findings())
    assert [f.id for f in out.findings] == [
        "todo_age:z.py:1-1",
        "churn:a.py:2-2",
        "churn:a.py:9-9",
        "churn:b.py:1-1",
    ]
    assert out.snapshot_id == SNAP_ID


def test_filters() -> None:
    fs = [
        _finding("churn", "a.py", 1, 0.2),
        _finding("churn", "b.py", 1, 0.8),
        _finding("todo_age", "b.py", 3, 0.6),
    ]
    t = _tools(fs)
    assert _ok(t.list_findings({"analyzer": "todo_age"})).total_matching == 1
    assert _ok(t.list_findings({"file": "b.py"})).total_matching == 2
    assert _ok(t.list_findings({"min_severity": 0.6})).total_matching == 2
    assert (
        _ok(
            t.list_findings({"analyzer": "churn", "file": "b.py", "min_severity": 0.5})
        ).total_matching
        == 1
    )


def test_default_limit_and_clamp_flag() -> None:
    t = _tools([_finding("churn", f"f{i:03}.py", 1, 0.5) for i in range(150)])
    default = _ok(t.list_findings())
    assert (len(default.findings), default.limit_applied, default.clamped) == (
        20,
        20,
        False,
    )
    assert default.total_matching == 150
    over = _ok(t.list_findings({"limit": 500}))
    assert (len(over.findings), over.limit_applied, over.clamped) == (100, 100, True)
    exact = _ok(t.list_findings({"limit": 100}))
    assert exact.clamped is False


def test_skipped_and_failed_analyzers_visible_when_empty() -> None:
    statuses = [
        AnalyzerStatus(name="churn", state="skipped", reason="no history"),
        AnalyzerStatus(name="todo_age", state="failed", reason="boom"),
        AnalyzerStatus(name="staleness", state="ok", total_found=0),
    ]
    out = _ok(_tools([], statuses).list_findings())
    assert out.findings == []
    assert {a.name: a.state for a in out.analyzers} == {
        "churn": "skipped",
        "todo_age": "failed",
        "staleness": "ok",
    }
    filtered = _ok(_tools([], statuses).list_findings({"analyzer": "churn"}))
    assert len(filtered.analyzers) == 3


def test_invalid_arguments() -> None:
    t = _tools([])
    for args in (
        {"min_severity": 1.5},
        {"min_severity": "high"},
        {"limit": 0},
        {"bogus": 1},
    ):
        res = t.list_findings(args)
        assert isinstance(res, ErrorResponse)
        assert res.error.code is ErrorCode.INVALID_ARGUMENT
        assert res.snapshot_id == SNAP_ID
