import re
import stat

import pytest

from skeleton.ingest.clone import clone_and_pin
from skeleton.ingest.models import IngestCode, IngestError, IngestLimits
from tests.fixtures.make_repo import FixtureRepo

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LIMITS = IngestLimits()


@pytest.fixture
def repo(tmp_path):
    r = FixtureRepo(tmp_path / "src")
    r.commit({"a.py": "a = 1\n"})
    r.commit({"b.py": "b = 2\n"})
    r._git("tag", "v1")
    r.branch("feature")
    r.commit({"c.py": "c = 3\n"})
    r.checkout("main")
    return r


def _clone(repo, dest, **kw):
    kw.setdefault("ref", None)
    kw.setdefault("sha", None)
    kw.setdefault("limits", LIMITS)
    return clone_and_pin(
        f"file://{repo.path}", dest=dest, _allow_protocols="file", **kw
    )


def test_default_branch_and_tag_resolve(repo, tmp_path):
    got = _clone(repo, tmp_path / "d1")
    assert SHA_RE.match(got) and got == repo.head()
    assert _clone(repo, tmp_path / "d2", ref="v1") == repo.head()


def test_branch_ref_resolves(repo, tmp_path):
    repo.checkout("feature")
    feature_head = repo.head()
    repo.checkout("main")
    got = _clone(repo, tmp_path / "d", ref="origin/feature")
    assert SHA_RE.match(got) and got == feature_head


def test_explicit_sha_pins(repo, tmp_path):
    first = repo.log_shas()[-1]
    assert _clone(repo, tmp_path / "d", sha=first) == first


def test_missing_sha_is_ref_not_found(repo, tmp_path):
    dest = tmp_path / "d"
    with pytest.raises(IngestError) as ei:
        _clone(repo, dest, sha="0" * 40)
    assert ei.value.code == IngestCode.ref_not_found
    assert not dest.exists()


def test_missing_ref_is_ref_not_found(repo, tmp_path):
    with pytest.raises(IngestError) as ei:
        _clone(repo, tmp_path / "d", ref="nope")
    assert ei.value.code == IngestCode.ref_not_found


def _stub(tmp_path, body):
    p = tmp_path / "stubgit"
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return str(p)


def test_timeout_kills_and_cleans(repo, tmp_path):
    dest = tmp_path / "d"
    stub = _stub(tmp_path, 'for last; do :; done\nmkdir -p "$last"\nsleep 30\n')
    with pytest.raises(IngestError) as ei:
        _clone(repo, dest, git_bin=stub, limits=IngestLimits(clone_timeout_s=1))
    assert ei.value.code == IngestCode.clone_timeout
    assert not dest.exists()


def test_size_limit_kills_and_cleans(repo, tmp_path):
    dest = tmp_path / "d"
    stub = _stub(
        tmp_path,
        'for last; do :; done\nmkdir -p "$last"\n'
        'head -c 200000 /dev/zero > "$last/blob"\nsleep 30\n',
    )
    with pytest.raises(IngestError) as ei:
        _clone(repo, dest, git_bin=stub, limits=IngestLimits(max_bytes=1000))
    assert ei.value.code == IngestCode.size_limit_exceeded
    assert not dest.exists()


def test_file_limit(repo, tmp_path):
    dest = tmp_path / "d"
    with pytest.raises(IngestError) as ei:
        _clone(repo, dest, limits=IngestLimits(max_files=1))
    assert ei.value.code == IngestCode.file_limit_exceeded
    assert not dest.exists()


def test_hooks_never_run(repo, tmp_path):
    marker = tmp_path / "ran"
    for name in ("post-checkout", "post-commit", "post-merge", "pre-commit", "post-update"):
        hook = repo.path / ".git" / "hooks" / name
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
    _clone(repo, tmp_path / "d")
    assert not marker.exists()
