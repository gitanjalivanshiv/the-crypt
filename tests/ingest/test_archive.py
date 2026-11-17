"""Archive ingest: safety, limits, layout, history."""

import hashlib
import io
import os
import stat
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest

from skeleton.ingest import IngestLimits, ingest_archive
from skeleton.ingest.models import IngestCode, IngestError
from tests.fixtures.make_repo import FixtureRepo

MIT = (
    "MIT License\n\nPermission is hereby granted, free of charge, to any person "
    "obtaining a copy of this software, to deal in the Software without restriction.\n"
)


@pytest.fixture
def store(tmp_path: Path):
    s = tmp_path / "store"
    yield s
    for root, dirs, files in os.walk(s):
        for n in [*dirs, *files]:
            p = os.path.join(root, n)
            if not os.path.islink(p):
                os.chmod(p, os.lstat(p).st_mode | stat.S_IWUSR)


def make_zip(entries: dict[str, str | bytes], symlinks: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
        for name, target in (symlinks or {}).items():
            zi = zipfile.ZipInfo(name)
            zi.create_system = 3
            zi.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(zi, target)
    return buf.getvalue()


def make_tgz(entries: dict[str, str | bytes], extra: list[tarfile.TarInfo] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in entries.items():
            raw = content.encode() if isinstance(content, str) else content
            ti = tarfile.TarInfo(name)
            ti.size = len(raw)
            tf.addfile(ti, io.BytesIO(raw))
        for ti in extra or []:
            tf.addfile(ti)
    return buf.getvalue()


def link(name: str, target: str, kind: bytes) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name)
    ti.type = kind
    ti.linkname = target
    return ti


def unsafe(data: bytes, store: Path, filename: str = "x.zip") -> None:
    with pytest.raises(IngestError) as e:
        ingest_archive(data, filename=filename, store=store)
    assert e.value.code is IngestCode.unsafe_archive
    assert not [p for p in store.rglob("*") if p.name == "meta.json"]
    assert not [p for p in store.glob(".staging-*")]


def test_zip_slip(store):
    unsafe(make_zip({"proj/a.py": "x=1\n", "proj/../../evil.py": "x"}), store)
    assert not (store.parent / "evil.py").exists()


def test_absolute_name(store):
    unsafe(make_zip({"/etc/evil.py": "x"}), store)
    unsafe(make_tgz({"/etc/evil.py": "x"}), store, "x.tar.gz")


def test_symlink_out_zip_and_tar(store):
    unsafe(make_zip({"p/a.py": "x"}, {"p/l": "../../etc"}), store)
    unsafe(make_zip({"p/a.py": "x"}, {"p/l": "/etc/passwd"}), store)
    unsafe(make_tgz({"p/a.py": "x"}, [link("p/l", "../../x", tarfile.SYMTYPE)]), store, "x.tgz")


def test_symlink_chain_escape(store):
    data = make_tgz(
        {"p/a.py": "x"},
        [link("p/d", "sub", tarfile.SYMTYPE), link("p/sub", "..", tarfile.SYMTYPE)],
    )
    # p/sub -> .. stays lexically inside the archive root, but then escapes the
    # stripped repo root; the on-disk check must catch it.
    unsafe(data, store, "x.tgz")


def test_hardlink_out(store):
    unsafe(make_tgz({"p/a.py": "x"}, [link("p/h", "../../etc/passwd", tarfile.LNKTYPE)]), store, "x.tgz")
    unsafe(make_tgz({"p/a.py": "x"}, [link("p/h", "/etc/passwd", tarfile.LNKTYPE)]), store, "x.tgz")


def test_hardlink_inside_is_copied(store):
    data = make_tgz({"p/a.py": "x = 1\n"}, [link("p/b.py", "p/a.py", tarfile.LNKTYPE)])
    snap = ingest_archive(data, filename="x.tgz", store=store)
    assert snap.read_bytes("b.py") == b"x = 1\n"


def test_duplicate_member_rejected(store):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for _ in range(2):
            ti = tarfile.TarInfo("p/a.py")
            ti.size = 1
            tf.addfile(ti, io.BytesIO(b"x"))
    unsafe(buf.getvalue(), store, "x.tgz")


def test_decompression_bomb_honest_header(store):
    data = make_zip({"p/big.txt": b"\0" * (5 * 1024 * 1024)})
    assert len(data) < 100_000
    with pytest.raises(IngestError) as e:
        ingest_archive(data, filename="b.zip", store=store, limits=IngestLimits(max_bytes=1024 * 1024))
    assert e.value.code is IngestCode.size_limit_exceeded
    assert not list(store.glob(".staging-*"))


def test_decompression_bomb_tar(store):
    data = make_tgz({"p/big.txt": b"\0" * (5 * 1024 * 1024)})
    with pytest.raises(IngestError) as e:
        ingest_archive(data, filename="b.tgz", store=store, limits=IngestLimits(max_bytes=1024 * 1024))
    assert e.value.code is IngestCode.size_limit_exceeded


def test_lying_zip_header_never_extracts_oversize(store):
    data = bytearray(make_zip({"p/big.txt": b"\0" * (5 * 1024 * 1024)}))
    # Patch uncompressed size (local header offset 22, central directory offset 24) to 10.
    lo = data.index(b"PK\x03\x04")
    struct.pack_into("<I", data, lo + 22, 10)
    co = data.index(b"PK\x01\x02")
    struct.pack_into("<I", data, co + 24, 10)
    with pytest.raises(IngestError):
        ingest_archive(bytes(data), filename="b.zip", store=store,
                       limits=IngestLimits(max_bytes=1024 * 1024))
    assert not list(store.glob(".staging-*"))
    assert not list(store.rglob("big.txt"))


def test_file_limit(store):
    data = make_zip({f"p/f{i}.py": "x" for i in range(5)})
    with pytest.raises(IngestError) as e:
        ingest_archive(data, filename="a.zip", store=store, limits=IngestLimits(max_files=3))
    assert e.value.code is IngestCode.file_limit_exceeded


@pytest.mark.parametrize("data", [b"just some text", b"", b"\x1f\x8b" + b"junk" * 10, b"PK\x03\x04junk"])
def test_unsupported_format(store, data):
    with pytest.raises(IngestError) as e:
        ingest_archive(data, filename="x.zip", store=store)
    assert e.value.code is IngestCode.invalid_source


def test_sniffs_content_not_extension(store):
    snap = ingest_archive(make_zip({"a.py": "x = 1\n"}), filename="whatever.bin", store=store)
    assert [f.path for f in snap.graph.files] == ["a.py"]


def test_github_style_top_level_stripped_and_sha256_id(store):
    data = make_zip({"repo-main/LICENSE": MIT, "repo-main/a.py": "import b\n", "repo-main/b.py": "x = 1\n"})
    snap = ingest_archive(data, filename="repo-main.zip", intent="retained", store=store)
    assert sorted(f.path for f in snap.graph.files) == ["LICENSE", "a.py", "b.py"]
    assert snap.meta.snapshot_id == "sha256:" + hashlib.sha256(data).hexdigest()
    assert snap.meta.licence == "MIT" and snap.meta.retainable
    assert snap.meta.history_available is False
    assert all(f.history is None for f in snap.graph.files)
    assert snap.root == store / "retained" / snap.meta.snapshot_id.replace(":", "-")
    assert snap.read_bytes("b.py") == b"x = 1\n"


def test_flat_archive_not_stripped_ephemeral(store):
    snap = ingest_archive(make_tgz({"a.py": "x\n", "d/b.py": "y\n"}), filename="f.tar.gz", store=store)
    assert sorted(f.path for f in snap.graph.files) == ["a.py", "d/b.py"]
    assert snap.root.parent == store / "ephemeral"


def test_streamed_file_object(store):
    data = make_zip({"a.py": "x\n"})
    snap = ingest_archive(io.BytesIO(data), filename="a.zip", store=store)
    assert snap.meta.snapshot_id == "sha256:" + hashlib.sha256(data).hexdigest()


def test_retained_gate_applies(store):
    with pytest.raises(IngestError) as e:
        ingest_archive(make_zip({"a.py": "x\n"}), filename="a.zip", intent="retained", store=store)
    assert e.value.code is IngestCode.licence_not_permitted
    assert not list(store.glob(".staging-*"))


def _tar_dir(src: Path, prefix: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(src, arcname=prefix)
    return buf.getvalue()


def test_archive_with_git_uses_head_and_history(store, tmp_path):
    repo = FixtureRepo(tmp_path / "src")
    repo.commit({"LICENSE": MIT, "a.py": "x = 1\n"}, date="2024-01-01T00:00:00+0000")
    sha = repo.commit({"a.py": "x = 2\n"}, date="2024-02-01T00:00:00+0000")
    snap = ingest_archive(_tar_dir(repo.path, "proj"), filename="proj.tgz", store=store)
    assert snap.meta.snapshot_id == sha
    assert snap.meta.history_available is True
    a = snap.entry("a.py")
    assert a is not None and a.history is not None and a.history.commit_count == 2
    assert not any(f.path.startswith(".git/") for f in snap.graph.files)


def test_archive_git_config_and_hooks_neutralised(store, tmp_path):
    repo = FixtureRepo(tmp_path / "src")
    repo.commit({"a.py": "x = 1\n"})
    hooks = repo.path / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "post-checkout").write_text("#!/bin/sh\ntouch /tmp/pwned-by-archive\n")
    with open(repo.path / ".git" / "config", "a", encoding="utf-8") as fh:
        fh.write("[core]\n\tfsmonitor = touch /tmp/pwned-by-archive\n")
    snap = ingest_archive(_tar_dir(repo.path, "proj"), filename="p.tgz", store=store)
    assert not (snap.repo / ".git" / "hooks").exists()
    assert "fsmonitor" not in (snap.repo / ".git" / "config").read_text()
    assert not Path("/tmp/pwned-by-archive").exists()


def test_archive_without_git_has_no_history(store):
    snap = ingest_archive(make_tgz({"p/a.py": "x\n", "p/b.py": "y\n"}), filename="p.tgz", store=store)
    assert snap.meta.history_available is False
    assert snap.meta.snapshot_id.startswith("sha256:")
    assert snap.meta.pinned_commit_time is None
    assert snap.graph.files and all(f.history is None for f in snap.graph.files)
