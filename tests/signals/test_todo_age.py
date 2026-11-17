"""todo_age tests.

Blame semantics (D10): `age_days` is "days since this line last changed", not
"days since the TODO text was first introduced".
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals import ANALYZERS, SignalsConfig, run_all
from skeleton.signals.todo_age import TodoAge, parse_blame, todo_severity
from tests.fixtures.make_repo import FixtureRepo

OLD = "2020-01-01T00:00:00+0000"
NEW = "2024-01-01T00:00:00+0000"


def build(tmp_path: Path, commits: list[tuple[str, dict[str, str]]]) -> Snapshot:
    """Commit each (date, files) in order and wrap the final tree as a Snapshot."""
    root = tmp_path / "snap"
    repo = FixtureRepo(root / "repo")
    sha = ""
    for date, files in commits:
        sha = repo.commit(files, date=date)
    pinned = int(
        subprocess.run(
            ["git", "show", "-s", "--format=%ct", sha],
            cwd=repo.path, capture_output=True, text=True, check=True,
        ).stdout
    )
    entries = []
    for p in sorted(repo.path.rglob("*.py")):
        data = p.read_bytes()
        entries.append(
            FileEntry(
                path=p.relative_to(repo.path).as_posix(),
                size_bytes=len(data),
                line_count=len(data.splitlines()),
                is_symlink=False,
                parsed=True,
                decodable=True,
                has_syntax_errors=False,
                history=None,
            )
        )
    meta = SnapshotMeta(
        snapshot_id=sha,
        source="x",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime.now(UTC),
        file_count=len(entries),
        total_bytes=0,
        pinned_commit_time=datetime.fromtimestamp(pinned, tz=UTC),
    )
    return Snapshot(root, meta, CodeGraph(files=entries, symbols={}, imports={}))


@pytest.fixture
def blame_spy(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []
    real = subprocess.run

    def spy(cmd, *a, **kw):  # type: ignore[no-untyped-def]
        if cmd[:2] == ["git", "blame"]:
            calls.append(list(cmd))
        return real(cmd, *a, **kw)

    monkeypatch.setattr("skeleton.signals.todo_age.subprocess.run", spy)
    return calls


def test_marker_in_string_not_reported_and_comment_is(tmp_path: Path) -> None:
    src = 's = "TODO: not a comment"\nx = 1  # FIXME later\n# todo lowercase\n# TODOS\n'
    snap = build(tmp_path, [(OLD, {"a.py": src})])
    out = TodoAge().analyze(snap, SignalsConfig())
    assert [(f.line_start, f.evidence) for f in out.findings] == [(2, "x = 1  # FIXME later")]


def test_age_and_true_count_and_blame_semantics(tmp_path: Path) -> None:
    old = "# TODO old\nx = 1\n"
    new = old + "# HACK new\n# XXX newer\n"
    snap = build(tmp_path, [(OLD, {"a.py": old}), (NEW, {"a.py": new})])
    out = TodoAge().analyze(snap, SignalsConfig())
    by_line = {f.line_start: f for f in out.findings}
    assert by_line[1].metrics["age_days"] == (
        datetime(2024, 1, 1) - datetime(2020, 1, 1)
    ).days
    assert by_line[3].metrics["age_days"] == 0
    assert all(f.metrics["todo_count_in_file"] == 3 for f in out.findings)
    assert by_line[1].severity == pytest.approx(1461 / 1825)
    assert by_line[3].severity == 0.0
    assert out.truncated is False


def test_one_blame_per_file_with_markers_only(
    tmp_path: Path, blame_spy: list[list[str]]
) -> None:
    snap = build(
        tmp_path,
        [(OLD, {"a.py": "# TODO a\n# TODO b\n", "b.py": "x = 1\n", "c.py": "# FIXME\n"})],
    )
    out = TodoAge().analyze(snap, SignalsConfig())
    assert len(out.findings) == 3
    assert len(blame_spy) == 2
    assert {c[-1] for c in blame_spy} == {"a.py", "c.py"}
    assert all(c[:3] == ["git", "blame", "--porcelain"] and c[-2] == "--" for c in blame_spy)


def test_cap_takes_whole_files_and_reports_total(tmp_path: Path) -> None:
    files = {
        "a.py": "# TODO 1\n# TODO 2\n",
        "b.py": "# TODO 3\n# TODO 4\n",
        "c.py": "# TODO 5\n",
    }
    snap = build(tmp_path, [(OLD, files)])
    out = TodoAge().analyze(snap, SignalsConfig(todo_max_markers=3))
    assert {f.file for f in out.findings} == {"a.py"}
    assert out.truncated is True
    assert out.total_found == 5
    assert all(f.metrics["todo_count_in_file"] == 2 for f in out.findings)


def test_run_all_status_and_registry(tmp_path: Path) -> None:
    assert [a.name for a in ANALYZERS] == ["churn", "staleness", "todo_age"]
    assert TodoAge.needs_history is True
    snap = build(tmp_path, [(OLD, {"a.py": "# TODO\n"})])
    result = run_all(snap, SignalsConfig(), [TodoAge()])
    assert result.analyzers[0].state == "ok"
    assert len(result.findings) == 1


def test_parse_blame_reuses_commit_time_for_later_lines() -> None:
    sha = "a" * 40
    out = (
        f"{sha} 1 1 2\ncommitter-time 100\nfilename x\n\tl1\n{sha} 2 2\n\tl2\n"
    ).encode()
    assert parse_blame(out) == {1: 100, 2: 100}


@given(st.integers(0, 20000), st.integers(0, 20000))
def test_severity_monotone_and_bounded(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    assert 0.0 <= todo_severity(lo, 1825) <= todo_severity(hi, 1825) <= 1.0
