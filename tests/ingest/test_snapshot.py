import os
from datetime import UTC, datetime
from pathlib import Path

from skeleton.ingest.models import CodeGraph, FileEntry, SnapshotMeta
from skeleton.ingest.snapshot import Snapshot


def _fe(path: str, is_symlink: bool = False) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=1,
        line_count=1,
        is_symlink=is_symlink,
        parsed=True,
        decodable=True,
        has_syntax_errors=False,
        history=None,
    )


def _make(tmp_path: Path) -> Snapshot:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "real").mkdir()
    (repo / "real" / "inner.py").write_text("x = 1\n")
    (repo / "src" / "a.py").write_text("print(1)\n")
    os.symlink("a.py", repo / "src" / "link.py")
    os.symlink("real", repo / "dirlink")
    meta = SnapshotMeta(
        snapshot_id="abc1234",
        source="x",
        licence="MIT",
        retainable=True,
        intent="ephemeral",
        history_available=False,
        ingested_at=datetime.now(UTC),
        file_count=2,
        total_bytes=2,
        pinned_commit_time=None,
    )
    graph = CodeGraph(
        files=[_fe("src/a.py"), _fe("src/link.py", True)], symbols={}, imports={}
    )
    (tmp_path / "meta.json").write_text(meta.model_dump_json())
    (tmp_path / "graph.json").write_text(graph.model_dump_json())
    return Snapshot.open(tmp_path)


def test_open_loads_models(tmp_path):
    snap = _make(tmp_path)
    assert snap.meta.snapshot_id == "abc1234"
    assert len(snap.graph.files) == 2


def test_entry_kind_exact_match(tmp_path):
    snap = _make(tmp_path)
    assert snap.entry_kind("src/a.py") == "file"
    assert snap.entry_kind("src/link.py") == "symlink"
    assert snap.entry_kind("a.py") is None
    assert snap.entry_kind("src/A.py") is None


def test_directories_give_none(tmp_path):
    snap = _make(tmp_path)
    assert snap.entry_kind("src") is None
    assert snap.entry_kind("dirlink") is None


def test_symlinked_directory_ancestor_detected(tmp_path):
    snap = _make(tmp_path)
    assert snap.entry_kind("dirlink/inner.py") is None
    assert snap.has_symlink_ancestor("dirlink/inner.py")
    assert not snap.has_symlink_ancestor("src/a.py")
    assert not snap.has_symlink_ancestor("a.py")


def test_read_bytes(tmp_path):
    snap = _make(tmp_path)
    assert snap.read_bytes("src/a.py") == b"print(1)\n"
    assert snap.read_bytes("src/link.py") is None
    assert snap.read_bytes("dirlink/inner.py") is None


def test_read_bytes_vanished_file_is_none(tmp_path):
    snap = _make(tmp_path)
    (tmp_path / "repo" / "src" / "a.py").unlink()
    assert snap.read_bytes("src/a.py") is None
    assert snap.read_bytes("nope\x00") is None
