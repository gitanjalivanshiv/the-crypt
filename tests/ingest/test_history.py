from datetime import UTC, datetime

from skeleton.ingest.history import collect_history
from tests.fixtures.make_repo import FixtureRepo

ANN = "Ann <Ann@Example.com>"
BOB = "Bob <bob@example.com>"


def d(day: int) -> str:
    return f"2024-02-{day:02d}T00:00:00+0000"


def dt(day: int) -> datetime:
    return datetime(2024, 2, day, tzinfo=UTC)


def test_counts_authors_and_last_modified(tmp_path):
    r = FixtureRepo(tmp_path / "r")
    r.commit({"a.py": "1\n"}, author=ANN, date=d(1))
    r.commit({"a.py": "2\n", "b.py": "b\n"}, author=BOB, date=d(2))
    sha = r.commit({"a.py": "3\n"}, author="Ann <ann@example.com>", date=d(3))
    res = collect_history(r.path, sha)
    assert res.available
    assert res.pinned_commit_time == dt(3)
    a, b = res.files["a.py"], res.files["b.py"]
    assert (a.commit_count, a.author_count, a.last_modified) == (3, 2, dt(3))
    assert (b.commit_count, b.author_count, b.last_modified) == (1, 1, dt(2))


def test_rename_history_starts_at_rename(tmp_path):
    r = FixtureRepo(tmp_path / "r")
    r.commit({"a.py": "x\n"}, date=d(1))
    r.commit({"a.py": "y\n"}, date=d(2))
    sha = r.rename("a.py", "b.py", date=d(3))
    res = collect_history(r.path, sha)
    assert "a.py" not in res.files
    assert res.files["b.py"].commit_count == 1
    assert res.files["b.py"].last_modified == dt(3)


def test_merge_commit_lists_no_files(tmp_path):
    r = FixtureRepo(tmp_path / "r")
    r.commit({"a.py": "a\n"}, date=d(1))
    r.branch("feature")
    r.commit({"c.py": "c\n"}, author=BOB, date=d(2))
    r.checkout("main")
    r.commit({"d.py": "d\n"}, date=d(3))
    sha = r.merge("feature", author=BOB, date=d(4))
    res = collect_history(r.path, sha)
    assert res.files["c.py"].commit_count == 1
    assert res.files["d.py"].commit_count == 1
    assert res.files["c.py"].author_count == 1
    assert res.files["d.py"].author_count == 1
    assert res.pinned_commit_time == dt(4)


def test_deleted_files_dropped(tmp_path):
    r = FixtureRepo(tmp_path / "r")
    r.commit({"a.py": "a\n", "b.py": "b\n"}, date=d(1))
    sha = r.commit(delete=["a.py"], date=d(2))
    res = collect_history(r.path, sha)
    assert set(res.files) == {"b.py"}


def test_date_order_independence(tmp_path):
    r = FixtureRepo(tmp_path / "r")
    r.commit({"a.py": "1\n"}, date=d(10))
    sha = r.commit({"a.py": "2\n"}, date=d(5))  # newer in topo order, older date
    res = collect_history(r.path, sha)
    assert res.files["a.py"].last_modified == dt(5)
    assert res.files["a.py"].commit_count == 2


def test_unavailable_never_raises(tmp_path):
    (tmp_path / "empty").mkdir()
    res = collect_history(tmp_path / "empty", "0" * 40)
    assert not res.available
    assert res.files == {}
    assert res.pinned_commit_time is None
    assert not collect_history(tmp_path / "missing", "HEAD").available
