"""Findings store and AnalysedSnapshot on a real ingested fixture snapshot."""

from pathlib import Path

import pytest

from skeleton.ingest import ingest_url
from skeleton.signals import Finding, FindingSet, finding_id
from skeleton.signals.store import AnalysedSnapshot, analyse, load_findings
from skeleton.verify.citation import CitationOk, Rejection, verify_citation
from skeleton.verify.codes import ReasonCode
from skeleton.verify.models import SnapshotView
from tests.fixtures.make_repo import FixtureRepo

URL = "https://example.com/owner/repo.git"
MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)
OLD = "2015-01-01T00:00:00+0000"


def _public(_host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def snap_dir(tmp_path: Path) -> Path:
    repo = FixtureRepo(tmp_path / "src")
    repo.commit({"LICENSE": MIT, "a.py": "x = 1\n# TODO: fix this\ny = 2\n"}, date=OLD)
    wrapper = tmp_path / "git-wrapper.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        f'  if [ "$a" = "{URL}" ]; then a="{repo.path}"; fi\n'
        '  set -- "$@" "$a"; shift\n'
        "done\n"
        'exec git "$@"\n'
    )
    wrapper.chmod(0o755)
    snap = ingest_url(
        URL,
        store=tmp_path / "store",
        resolver=_public,
        git_bin=str(wrapper),
        _allow_protocols="file",
    )
    return snap.root


def test_round_trip(snap_dir: Path) -> None:
    result = analyse(snap_dir)
    assert (snap_dir / "findings.json").is_file()
    assert load_findings(snap_dir) == result
    assert isinstance(result, FindingSet)
    assert any(f.analyzer == "todo_age" for f in result.findings)


def test_finding_known_and_unknown(snap_dir: Path) -> None:
    analyse(snap_dir)
    view = AnalysedSnapshot.open(snap_dir)
    f: Finding = view.findings.findings[0]
    assert view.finding(finding_id(f)) == (f.file, f.metrics)
    assert view.finding("nope:a.py:1-1") is None


def test_satisfies_snapshot_view_and_verifies_citation(snap_dir: Path) -> None:
    analyse(snap_dir)
    view: SnapshotView = AnalysedSnapshot.open(snap_dir)
    assert view.snapshot_id == AnalysedSnapshot.open(snap_dir).snapshot.meta.snapshot_id
    ok = verify_citation(
        view,
        {"file": "a.py", "line_start": 2, "line_end": 2, "quote": "# TODO: fix this"},
    )
    assert isinstance(ok, CitationOk)
    bad = verify_citation(
        view, {"file": "missing.py", "line_start": 1, "line_end": 1, "quote": None}
    )
    assert isinstance(bad, Rejection) and bad.code is ReasonCode.FILE_NOT_FOUND
