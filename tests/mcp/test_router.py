"""ToolRouter allow-list behaviour (R5.6, R5.7)."""

import re
from datetime import UTC, datetime
from pathlib import Path

from skeleton.ingest.models import CodeGraph, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.contract import (
    TOOL_NAMES,
    ErrorCode,
    ErrorResponse,
    GetSnapshotOutput,
    ListFindingsOutput,
)
from skeleton.mcp.router import ToolRouter
from skeleton.mcp.tools import SignalTools
from skeleton.signals.models import AnalyzerStatus, FindingSet
from skeleton.signals.store import AnalysedSnapshot

SNAP_ID = "a" * 40


def _tools() -> SignalTools:
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="https://example.com/r.git",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=0,
        total_bytes=0,
        pinned_commit_time=None,
    )
    snap = Snapshot(Path("."), meta, CodeGraph(files=[], symbols={}, imports={}))
    findings = FindingSet(
        snapshot_id=SNAP_ID,
        findings=[],
        analyzers=[AnalyzerStatus(name="churn", state="ok", total_found=0)],
    )
    return SignalTools(AnalysedSnapshot(snap, findings))


def _code(result: object) -> ErrorCode:
    assert isinstance(result, ErrorResponse)
    return result.error.code


def test_unrestricted_lists_all_tools() -> None:
    assert ToolRouter(_tools(), None).tool_names == sorted(TOOL_NAMES)


def test_restricted_listing() -> None:
    router = ToolRouter(_tools(), ["list_findings", "get_snapshot", "bogus"])
    assert router.tool_names == ["get_snapshot", "list_findings"]


def test_empty_allow_list_exposes_nothing() -> None:
    router = ToolRouter(_tools(), [])
    assert router.tool_names == []
    assert _code(router.call("get_snapshot")) == ErrorCode.TOOL_NOT_ALLOWED


def test_allowed_calls_dispatch() -> None:
    router = ToolRouter(_tools(), ["get_snapshot", "list_findings"])
    assert isinstance(router.call("get_snapshot"), GetSnapshotOutput)
    assert isinstance(router.call("list_findings", {}), ListFindingsOutput)


def test_disallowed_tool_rejected() -> None:
    router = ToolRouter(_tools(), ["get_snapshot"])
    result = router.call("read_lines", {"file": "a.py", "line_start": 1, "line_end": 1})
    assert _code(result) == ErrorCode.TOOL_NOT_ALLOWED
    assert isinstance(result, ErrorResponse) and result.snapshot_id == SNAP_ID


def test_unknown_tool_is_invalid_argument() -> None:
    router = ToolRouter(_tools(), ["get_snapshot"])
    assert _code(router.call("write_file", {})) == ErrorCode.INVALID_ARGUMENT
    assert _code(ToolRouter(_tools(), None).call("nope")) == ErrorCode.INVALID_ARGUMENT


def test_bad_arguments_return_structured_error() -> None:
    router = ToolRouter(_tools(), None)
    assert _code(router.call("get_snapshot", {"x": 1})) == ErrorCode.INVALID_ARGUMENT
    assert _code(router.call("read_lines", {"file": 3})) == ErrorCode.INVALID_ARGUMENT
    assert _code(router.call("get_file_facts", None)) == ErrorCode.INVALID_ARGUMENT


def test_no_write_execute_or_network_tool() -> None:
    forbidden = re.compile(
        r"write|exec|run|shell|delete|remove|create|edit|fetch|http|url|download|network|clone",
        re.IGNORECASE,
    )
    names = ToolRouter(_tools(), None).tool_names
    assert names
    assert not [n for n in names if forbidden.search(n)]
    assert set(names) == TOOL_NAMES
