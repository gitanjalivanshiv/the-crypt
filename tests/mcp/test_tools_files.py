"""SignalTools get_file_facts and read_lines against a real directory snapshot."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skeleton.ingest.models import (
    CodeGraph,
    FileEntry,
    FileHistory,
    Import,
    SnapshotMeta,
    Symbol,
)
from skeleton.ingest.snapshot import Snapshot
from skeleton.mcp.contract import (
    READ_LINES_MAX,
    ErrorCode,
    ErrorResponse,
    GetFileFactsOutput,
    ReadLinesOutput,
)
from skeleton.mcp.tools import SignalTools
from skeleton.signals.models import FindingSet
from skeleton.signals.store import AnalysedSnapshot

SNAP_ID = "b" * 40


def _entry(path: str, lines: int, *, symlink: bool = False, hist: bool = False) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=1,
        line_count=lines,
        is_symlink=symlink,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=FileHistory(
            commit_count=3, last_modified=datetime(2024, 1, 1, tzinfo=UTC), author_count=2
        )
        if hist
        else None,
    )


@pytest.fixture
def tools(tmp_path: Path) -> SignalTools:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "a.py").write_text("one  \r\ntwo\t\nthree\n")
    (repo / "pkg" / "h.py").write_text("x\n")
    (repo / "big.txt").write_text("".join(f"l{i}\n" for i in range(1, 251)))
    os.symlink("a.py", repo / "link.py")
    os.symlink("pkg", repo / "linkdir")
    graph = CodeGraph(
        files=[
            _entry("a.py", 3, hist=True),
            _entry("pkg/h.py", 1),
            _entry("big.txt", 250),
            _entry("link.py", 3, symlink=True),
        ],
        symbols={"a.py": [Symbol(name="f", kind="function", line_start=1, line_end=2)]},
        imports={
            "a.py": [Import(module="os", names=[], line=1, level=0, resolved_file=None)]
        },
    )
    meta = SnapshotMeta(
        snapshot_id=SNAP_ID,
        source="s",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
        file_count=4,
        total_bytes=10,
        pinned_commit_time=None,
    )
    snap = Snapshot(tmp_path, meta, graph)
    return SignalTools(
        AnalysedSnapshot(snap, FindingSet(snapshot_id=SNAP_ID, findings=[], analyzers=[]))
    )


def test_file_facts(tools: SignalTools) -> None:
    out = tools.get_file_facts({"file": "a.py"})
    assert isinstance(out, GetFileFactsOutput)
    assert out.snapshot_id == SNAP_ID
    assert out.line_count == 3
    assert out.symbols[0].name == "f" and out.imports[0].module == "os"
    assert out.history is not None and out.history.commit_count == 3
    assert out.history_available is True


def test_file_without_history(tools: SignalTools) -> None:
    out = tools.get_file_facts({"file": "pkg/h.py"})
    assert isinstance(out, GetFileFactsOutput)
    assert out.history is None
    assert out.history_available is False


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"file": "../etc/passwd"}, ErrorCode.PATH_UNSAFE),
        ({"file": "/abs"}, ErrorCode.PATH_UNSAFE),
        ({"file": "link.py"}, ErrorCode.SYMLINK),
        ({"file": "linkdir/h.py"}, ErrorCode.SYMLINK),
        ({"file": "nope.py"}, ErrorCode.FILE_NOT_FOUND),
        ({}, ErrorCode.INVALID_ARGUMENT),
    ],
)
def test_file_facts_errors(tools: SignalTools, args: dict[str, object], code: ErrorCode) -> None:
    out = tools.get_file_facts(args)
    assert isinstance(out, ErrorResponse)
    assert out.error.code == code
    assert out.snapshot_id == SNAP_ID


def test_read_lines_normalised(tools: SignalTools) -> None:
    out = tools.read_lines({"file": "a.py", "line_start": 1, "line_end": 2})
    assert isinstance(out, ReadLinesOutput)
    assert out.lines == ["one", "two"]
    assert (out.line_start, out.returned_line_end, out.truncated) == (1, 2, False)
    assert out.snapshot_id == SNAP_ID


@pytest.mark.parametrize(
    ("file", "start", "end", "code"),
    [
        ("../x", 1, 1, ErrorCode.PATH_UNSAFE),
        ("link.py", 1, 1, ErrorCode.SYMLINK),
        ("nope.py", 1, 1, ErrorCode.FILE_NOT_FOUND),
        ("a.py", 0, 1, ErrorCode.RANGE_INVALID),
        ("a.py", 3, 2, ErrorCode.RANGE_INVALID),
        ("a.py", 1, 4, ErrorCode.RANGE_OUT_OF_BOUNDS),
    ],
)
def test_read_lines_errors(
    tools: SignalTools, file: str, start: int, end: int, code: ErrorCode
) -> None:
    out = tools.read_lines({"file": file, "line_start": start, "line_end": end})
    assert isinstance(out, ErrorResponse)
    assert out.error.code == code
    assert out.snapshot_id == SNAP_ID


def test_read_lines_wrong_type(tools: SignalTools) -> None:
    out = tools.read_lines({"file": "a.py", "line_start": "1", "line_end": 2})
    assert isinstance(out, ErrorResponse)
    assert out.error.code == ErrorCode.INVALID_ARGUMENT


def test_read_lines_truncates_at_cap(tools: SignalTools) -> None:
    out = tools.read_lines({"file": "big.txt", "line_start": 1, "line_end": 250})
    assert isinstance(out, ReadLinesOutput)
    assert len(out.lines) == READ_LINES_MAX
    assert out.truncated is True
    assert out.returned_line_end == READ_LINES_MAX
    assert out.lines[-1] == "l200"


def test_read_lines_exactly_cap_not_truncated(tools: SignalTools) -> None:
    out = tools.read_lines({"file": "big.txt", "line_start": 51, "line_end": 250})
    assert isinstance(out, ReadLinesOutput)
    assert len(out.lines) == READ_LINES_MAX
    assert out.truncated is False
    assert out.returned_line_end == 250
