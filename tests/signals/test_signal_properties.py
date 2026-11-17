"""Property 10: signals invariants (R2.5, R2.6, R2.8, R2.9).

**Validates: Requirements 2.2, 2.3, 2.4, 2.6**

Edit EXPECTED_NAMES in the same commit as any analyzer cut (R2.8, R2.9).
"""

import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from skeleton.ingest.models import CodeGraph, FileEntry, FileHistory, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot
from skeleton.signals import ANALYZERS, SignalsConfig, run_all
from skeleton.signals.churn import Churn
from skeleton.signals.staleness import Staleness
from skeleton.signals.todo_age import TodoAge
from skeleton.verify.textnorm import normalised_lines
from tests.fixtures.make_repo import FixtureRepo

CFG = SignalsConfig()
PINNED = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

EXPECTED_NAMES = {"churn", "staleness", "todo_age"}
ABSENT_NAMES = {"complexity", "dependency_age", "dead_code"}


# ---------------------------------------------------------------- registry


def test_registry_names_match_expected_set() -> None:
    names = [a.name for a in ANALYZERS]
    assert len(names) == len(set(names))
    assert set(names) == EXPECTED_NAMES


def test_designed_only_analyzers_are_not_registered() -> None:
    assert not ABSENT_NAMES & {a.name for a in ANALYZERS}


# ---------------------------------------------------------------- strategies

_line = st.text(alphabet="abcxyz_ =():#\t", max_size=20)
_body = st.lists(_line, max_size=8)
_terminator = st.sampled_from(["\n", "\r\n", "\r"])


@st.composite
def file_texts(draw: st.DrawFn) -> str:
    lines = draw(_body)
    if draw(st.booleans()):
        lines = ['"""doc"""', *lines]
    elif draw(st.booleans()):
        lines = ["def f():", "    return 1", *lines]
    term = draw(_terminator)
    text = term.join(lines)
    return text + term if lines and draw(st.booleans()) else text


@st.composite
def history_files(draw: st.DrawFn) -> list[tuple[str, int, int]]:
    """(text, commit_count, days_since_modified) per file."""
    return draw(
        st.lists(
            st.tuples(file_texts(), st.integers(1, 400), st.integers(0, 6000)),
            min_size=1,
            max_size=6,
        )
    )


def _meta(snapshot_id: str, n: int, pinned: datetime) -> SnapshotMeta:
    return SnapshotMeta(
        snapshot_id=snapshot_id,
        source="x",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=True,
        ingested_at=datetime(2024, 7, 1, tzinfo=UTC),
        file_count=n,
        total_bytes=0,
        pinned_commit_time=pinned,
    )


def build_history_snapshot(root: Path, files: list[tuple[str, int, int]]) -> Snapshot:
    repo = root / "repo"
    repo.mkdir()
    entries = []
    for i, (text, commits, days) in enumerate(files):
        name = f"f{i}.py"
        data = text.encode()
        (repo / name).write_bytes(data)
        entries.append(
            FileEntry(
                path=name,
                size_bytes=len(data),
                line_count=len(normalised_lines(data)),
                is_symlink=False,
                parsed=True,
                decodable=True,
                has_syntax_errors=False,
                history=FileHistory(
                    commit_count=commits,
                    last_modified=PINNED - timedelta(days=days),
                    author_count=2,
                ),
            )
        )
    graph = CodeGraph(files=entries, symbols={}, imports={})
    return Snapshot(root, _meta("snap", len(entries), PINNED), graph)


# ---------------------------------------------------------------- invariants


def assert_invariants(snap: Snapshot, result) -> None:  # type: ignore[no-untyped-def]
    for f in result.findings:
        data = snap.read_bytes(f.file)
        assert data is not None
        lines = normalised_lines(data)
        assert 1 <= f.line_start <= f.line_end <= len(lines)
        assert f.evidence == "\n".join(lines[f.line_start - 1 : f.line_end])
        assert 0.0 <= f.severity <= 1.0


def assert_monotone(findings, key: str) -> None:  # type: ignore[no-untyped-def]
    for a in findings:
        for b in findings:
            if a.metrics[key] <= b.metrics[key]:
                assert a.severity <= b.severity


HISTORY_ANALYZERS = [(Churn(), "commit_count"), (Staleness(), "days_since_modified")]
_SETTINGS = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@_SETTINGS
@given(files=history_files())
def test_history_analyzers_findings_valid_monotone_and_deterministic(
    files: list[tuple[str, int, int]],
) -> None:
    with tempfile.TemporaryDirectory() as d:
        snap = build_history_snapshot(Path(d), files)
        for analyzer, metric in HISTORY_ANALYZERS:
            first = run_all(snap, CFG, [analyzer])
            second = run_all(snap, CFG, [analyzer])
            assert first.analyzers[0].state == "ok", first.analyzers[0].reason
            assert_invariants(snap, first)
            assert_monotone(first.findings, metric)
            assert first.model_dump() == second.model_dump()


# ---------------------------------------------------------------- todo_age

_BASE = datetime(2018, 1, 1, tzinfo=UTC)


@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    day_offsets=st.lists(st.integers(0, 2500), min_size=1, max_size=4),
    extra=st.lists(_line.filter(lambda s: "TODO" not in s), max_size=3),
)
def test_todo_age_valid_monotone_and_deterministic(
    day_offsets: list[int], extra: list[str]
) -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "snap"
        repo = FixtureRepo(root / "repo")
        sha = ""
        files: dict[str, str] = {}
        for i, off in enumerate(sorted(day_offsets)):
            when = (_BASE + timedelta(days=off)).strftime("%Y-%m-%dT%H:%M:%S+0000")
            files[f"m{i}.py"] = "\n".join([*extra, f"# TODO item {i}", "x = 1"]) + "\n"
            sha = repo.commit(dict(files), date=when)
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
                    line_count=len(normalised_lines(data)),
                    is_symlink=False,
                    parsed=True,
                    decodable=True,
                    has_syntax_errors=False,
                    history=None,
                )
            )
        meta = _meta(sha, len(entries), datetime.fromtimestamp(pinned, tz=UTC))
        snap = Snapshot(root, meta, CodeGraph(files=entries, symbols={}, imports={}))

        first = run_all(snap, CFG, [TodoAge()])
        second = run_all(snap, CFG, [TodoAge()])
        assert first.analyzers[0].state == "ok", first.analyzers[0].reason
        assert first.findings
        assert_invariants(snap, first)
        assert_monotone(first.findings, "age_days")
        assert first.model_dump() == second.model_dump()
