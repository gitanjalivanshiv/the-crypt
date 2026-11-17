"""FakeView and RealDirView agree; strategies only produce in-range citations."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from skeleton.verify.textnorm import normalised_lines, split_lines
from tests.verify.fake_view import FakeView, RealDirView
from tests.verify.strategies import answer, file_contents, file_trees, valid_citation

FILES = {"a.txt": b"one\ntwo\n", "dir/inner.txt": b"inner\n"}
SYMLINKS = {"link.txt": "a.txt"}
SYMLINK_DIRS = {"linkdir": "dir"}
FINDINGS = {"f1": ("a.txt", {"commit_count": 3})}

# path -> (entry_kind, has_symlink_ancestor, read_bytes)
CASES = {
    "a.txt": ("file", False, b"one\ntwo\n"),
    "link.txt": ("symlink", False, b"one\ntwo\n"),
    "linkdir/inner.txt": ("file", True, b"inner\n"),
    "missing.txt": (None, False, None),
    "dir": (None, False, None),
    "linkdir": ("symlink", False, None),
}


@pytest.fixture(params=["fake", "real"])
def view(request, tmp_path):
    kw = {"files": FILES, "symlinks": SYMLINKS, "symlink_dirs": SYMLINK_DIRS, "findings": FINDINGS}
    if request.param == "fake":
        return FakeView(**kw)
    return RealDirView(tmp_path, **kw)


@pytest.mark.parametrize("path", list(CASES))
def test_views_agree_on_shared_cases(view, path):
    kind, ancestor, data = CASES[path]
    assert view.entry_kind(path) == kind
    assert view.has_symlink_ancestor(path) is ancestor
    assert view.read_bytes(path) == data


def test_finding_lookup(view):
    assert view.finding("f1") == ("a.txt", {"commit_count": 3})
    assert view.finding("nope") is None


@settings(max_examples=50)
@given(file_trees().flatmap(lambda t: st.tuples(st.just(t), valid_citation(t))))
def test_citations_are_in_range(pair):
    tree, c = pair
    lines = split_lines(tree.files[c["file"]])
    assert 1 <= c["line_start"] <= c["line_end"] <= len(lines)
    expected = normalised_lines(tree.files[c["file"]])[c["line_start"] - 1 : c["line_end"]]
    assert c["quote"].split("\n") == expected


@settings(max_examples=50)
@given(file_trees().flatmap(lambda t: st.tuples(st.just(t), answer(t))))
def test_answer_citations_and_figures_valid(pair):
    tree, ans = pair
    assert ans["claims"]
    for claim in ans["claims"]:
        for c in claim["citations"]:
            assert 1 <= c["line_start"] <= c["line_end"] <= len(split_lines(tree.files[c["file"]]))
        for f in claim.get("figures", []):
            file, metrics = tree.findings[f["finding_id"]]
            assert metrics[f["key"]] == f["value"]
            assert file in {c["file"] for c in claim["citations"]}


@given(file_contents())
def test_file_contents_decode(data):
    data.decode("utf-8")
