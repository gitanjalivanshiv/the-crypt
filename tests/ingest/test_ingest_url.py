"""End-to-end URL ingest on a local fixture repo."""

import os
import stat
from pathlib import Path

import pytest

from skeleton.ingest import ingest_url
from skeleton.ingest.models import IngestCode, IngestError
from tests.fixtures.make_repo import FixtureRepo

URL = "https://example.com/owner/repo.git"
MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)
GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"


def _public(_host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def git_wrapper(tmp_path: Path):
    """Return a factory making a git wrapper that maps URL to a local repo path."""

    def make(local: Path) -> str:
        script = tmp_path / "git-wrapper.sh"
        script.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            f'  if [ "$a" = "{URL}" ]; then a="{local}"; fi\n'
            '  set -- "$@" "$a"; shift\n'
            "done\n"
            'exec git "$@"\n'
        )
        script.chmod(0o755)
        return str(script)

    return make


@pytest.fixture
def stores(tmp_path: Path):
    store = tmp_path / "store"
    yield store
    for root, dirs, files in os.walk(store):
        for n in [*dirs, *files]:
            p = os.path.join(root, n)
            if not os.path.islink(p):
                os.chmod(p, os.lstat(p).st_mode | stat.S_IWUSR)


def _repo(tmp_path: Path, licence: str) -> FixtureRepo:
    r = FixtureRepo(tmp_path / "src")
    r.commit({"LICENSE": licence, "a.py": "import b\n\ndef f():\n    pass\n", "b.py": "x = 1\n"},
             date="2024-01-01T00:00:00+0000")
    r.commit({"a.py": "import b\n\ndef f():\n    return 1\n"}, date="2024-02-01T00:00:00+0000")
    return r


def _run(tmp_path, store, git_wrapper, repo, **kw):
    return ingest_url(
        URL, ref=None, sha=None, store=store, resolver=_public,
        git_bin=git_wrapper(repo.path), _allow_protocols="file", **kw,
    )


def test_retained_mit_metadata_complete(tmp_path, stores, git_wrapper):
    repo = _repo(tmp_path, MIT)
    snap = _run(tmp_path, stores, git_wrapper, repo, intent="retained")
    m = snap.meta
    assert m.snapshot_id == repo.head()
    assert snap.root == stores / "retained" / repo.head()
    assert m.source == URL and m.licence == "MIT" and m.retainable
    assert m.intent == "retained" and m.history_available
    assert m.file_count == 3 and m.total_bytes > 0
    assert m.pinned_commit_time is not None and m.ingested_at is not None
    assert (snap.root / "graph.json").is_file()
    assert snap.entry("a.py").history.commit_count == 2
    assert snap.read_bytes("b.py") == b"x = 1\n"


def test_retained_gpl_fails_and_leaves_nothing(tmp_path, stores, git_wrapper):
    repo = _repo(tmp_path, GPL)
    with pytest.raises(IngestError) as ei:
        _run(tmp_path, stores, git_wrapper, repo, intent="retained")
    assert ei.value.code is IngestCode.licence_not_permitted
    assert list(stores.iterdir()) == []


def test_ephemeral_gpl_succeeds_not_retainable_and_default_intent(tmp_path, stores, git_wrapper):
    repo = _repo(tmp_path, GPL)
    snap = _run(tmp_path, stores, git_wrapper, repo)
    assert snap.meta.intent == "ephemeral"
    assert snap.meta.retainable is False
    assert snap.root.parent == stores / "ephemeral"
    assert snap.root.name != repo.head()


def test_graph_json_byte_identical_across_runs(tmp_path, stores, git_wrapper):
    repo = _repo(tmp_path, MIT)
    a = _run(tmp_path, stores, git_wrapper, repo)
    b = _run(tmp_path, stores, git_wrapper, repo)
    assert a.root != b.root
    assert (a.root / "graph.json").read_bytes() == (b.root / "graph.json").read_bytes()


def test_repo_is_read_only_afterwards(tmp_path, stores, git_wrapper):
    repo = _repo(tmp_path, MIT)
    snap = _run(tmp_path, stores, git_wrapper, repo)
    assert not os.access(snap.repo / "a.py", os.W_OK) or os.geteuid() == 0
    assert stat.S_IMODE(os.lstat(snap.repo / "a.py").st_mode) & 0o222 == 0
    assert stat.S_IMODE(os.lstat(snap.repo).st_mode) & 0o222 == 0


def test_invalid_url_rejected_before_io(tmp_path, stores):
    with pytest.raises(IngestError) as ei:
        ingest_url("http://example.com/x", ref=None, sha=None, store=stores)
    assert ei.value.code is IngestCode.invalid_source
    assert not stores.exists()
