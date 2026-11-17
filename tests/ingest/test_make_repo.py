import subprocess

from tests.fixtures.make_repo import FixtureRepo

A = "Ann <ann@example.com>"
B = "Bob <bob@example.com>"


def _script(path):
    r = FixtureRepo(path)
    r.commit({"a.py": "a\n"}, author=A, date="2024-01-01T00:00:00+0000")
    r.commit({"a.py": "a2\n"}, author=B, date="2024-02-01T00:00:00+0000")
    r.rename("a.py", "b.py", author=A, date="2024-03-01T00:00:00+0000")
    r.branch("feature")
    r.commit({"c.py": "c\n"}, author=B, date="2024-03-05T00:00:00+0000")
    r.checkout("main")
    r.commit({"d.py": "d\n"}, author=A, date="2024-03-06T00:00:00+0000")
    r.merge("feature", author=A, date="2024-03-07T00:00:00+0000")
    return r


def _git(r, *args):
    return subprocess.run(["git", *args], cwd=r.path, capture_output=True, text=True, check=True).stdout


def test_same_script_same_shas(tmp_path):
    one = _script(tmp_path / "one")
    two = _script(tmp_path / "two")
    assert one.log_shas() == two.log_shas()
    assert one.head() == two.head()


def test_dates_and_authors_as_scripted(tmp_path):
    r = _script(tmp_path)
    out = _git(r, "log", "--no-renames", "--format=%ae|%aI|%cI", "--reverse").splitlines()
    assert out[0] == "ann@example.com|2024-01-01T00:00:00Z|2024-01-01T00:00:00Z"
    assert out[1].startswith("bob@example.com|2024-02-01")
    assert len(out) == 6


def test_merge_lists_no_files_and_rename_is_delete_plus_add(tmp_path):
    r = _script(tmp_path)
    merge = _git(r, "log", "-1", "--format=%P", r.head()).split()
    assert len(merge) == 2
    assert _git(r, "log", "-1", "--name-only", "--format=", r.head()).strip() == ""
    files = _git(r, "log", "--no-renames", "--name-only", "--format=", "--grep=rename").split()
    assert sorted(files) == ["a.py", "b.py"]
    assert sorted(_git(r, "ls-files").split()) == ["b.py", "c.py", "d.py"]
