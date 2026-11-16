"""Claim properties P1, P6, P7 (design 12.1).

**Validates: Requirements 4.21, 4.10, 4.11**
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from skeleton.verify.codes import ReasonCode as R
from skeleton.verify.models import Banishment, VerifiedClaim, VerifyConfig
from skeleton.verify.claim import verify_claim
from skeleton.verify.textnorm import normalise_line, split_lines
from tests.verify.fake_view import FakeView
from tests.verify.strategies import answer, file_trees

CFG = settings(max_examples=200, deadline=None)
EMPTY = VerifyConfig()


def _expected_quote(data: bytes, start: int, end: int) -> str:
    lines = split_lines(data)[start - 1 : end]
    return "\n".join(b.decode("utf-8").rstrip(" \t\f\v") for b in lines)


# ---- P1 -------------------------------------------------------------------


@st.composite
def tree_and_answer(draw):
    tree = draw(file_trees())
    return tree, draw(answer(tree))


@CFG
@given(ta=tree_and_answer())
def test_p1_generated_answers_verify_and_citations_resolve(ta):
    tree, ans = ta
    view = FakeView(files=tree.files, findings=tree.findings)
    for raw in ans["claims"]:
        # By design (section 3), a quote whose last line is empty never matches.
        assume(all(c["quote"].split("\n")[-1] != "" for c in raw["citations"]))
    for raw in ans["claims"]:
        result = verify_claim(view, raw, 1, EMPTY)
        assert isinstance(result, VerifiedClaim), result
        for c in result.citations:
            assert c.file in tree.files
            n = len(split_lines(tree.files[c.file]))
            assert 1 <= c.line_start <= c.line_end <= n
            assert c.quote == _expected_quote(tree.files[c.file], c.line_start, c.line_end)
            assert c.quote == "\n".join(
                normalise_line(b.decode("utf-8"))
                for b in split_lines(tree.files[c.file])[c.line_start - 1 : c.line_end]
            )


# ---- P6 -------------------------------------------------------------------


@st.composite
def finding_claim(draw):
    """A view with a finding, plus a claim citing its file with a correct figure."""
    tree = draw(file_trees())
    fid = draw(st.sampled_from(sorted(tree.findings or {"x": None})))
    assume(tree.findings)
    path, metrics = tree.findings[fid]
    assume(split_lines(tree.files[path]))
    key = draw(st.sampled_from(sorted(metrics)))
    cite = {"file": path, "line_start": 1, "line_end": 1}
    view = FakeView(files=tree.files, findings=tree.findings)
    figure = {"finding_id": fid, "key": key, "value": metrics[key]}
    return view, cite, figure


def _claim(cite, figure):
    return {"text": "Notable churn here", "citations": [cite], "figures": [figure]}


@CFG
@given(fc=finding_claim())
def test_p6_exact_figure_verifies(fc):
    view, cite, figure = fc
    assert isinstance(verify_claim(view, _claim(cite, figure), 1, EMPTY), VerifiedClaim)


@CFG
@given(
    fc=finding_claim(),
    delta=st.sampled_from([1e-9, -1e-9, 1e-6, 0.001, 0.5, 1, -1, 7, 1000]),
)
def test_p6_figure_off_by_any_amount_is_not_in_metrics(fc, delta):
    view, cite, figure = fc
    off = figure["value"] + delta
    assume(off != figure["value"])
    result = verify_claim(view, _claim(cite, {**figure, "value": off}), 1, EMPTY)
    assert isinstance(result, Banishment)
    assert result.reason is R.FIGURE_NOT_IN_METRICS


# ---- P7 -------------------------------------------------------------------

_NUM = st.one_of(
    st.integers(0, 10**6),
    st.integers(1, 10**5).map(lambda k: k / 100),
)
_FILE = b"alpha\nbeta\ngamma\n"


def _view(value=None):
    findings = {"f1": ("a.py", {"k": value})} if value is not None else {}
    return FakeView(files={"a.py": _FILE}, findings=findings)


def _guess(text):
    return {"text": text, "guess": True}


@CFG
@given(n=_NUM)
def test_p7_unbacked_digit_token_is_rejected(n):
    token = repr(n)
    result = verify_claim(_view(), _guess(f"It handles {token} cases"), 1, EMPTY)
    assert isinstance(result, Banishment)
    assert result.reason is R.UNBACKED_NUMBER
    assert result.target.token == token


@CFG
@given(n=_NUM)
def test_p7_moving_number_into_verified_figure_passes(n):
    token = repr(n)
    raw = {
        "text": f"It handles {token} cases",
        "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}],
        "figures": [{"finding_id": "f1", "key": "k", "value": n}],
    }
    assert isinstance(verify_claim(_view(n), raw, 1, EMPTY), VerifiedClaim)


@CFG
@given(n=_NUM)
def test_p7_allow_list_backs_token(n):
    token = repr(n)
    cfg = VerifyConfig(allowed_numbers=frozenset({token}))
    assert isinstance(verify_claim(_view(), _guess(f"It handles {token} cases"), 1, cfg), VerifiedClaim)


@CFG
@given(n=st.integers(1, 3))
def test_p7_citation_line_number_backs_token(n):
    raw = {
        "text": f"See line {n}",
        "citations": [{"file": "a.py", "line_start": n, "line_end": n}],
    }
    assert isinstance(verify_claim(_view(), raw, 1, EMPTY), VerifiedClaim)


@CFG
@given(n=st.integers(4, 10**6))
def test_p7_token_not_a_cited_line_is_rejected(n):
    raw = {
        "text": f"See line {n}",
        "citations": [{"file": "a.py", "line_start": 1, "line_end": 3}],
    }
    result = verify_claim(_view(), raw, 1, EMPTY)
    assert isinstance(result, Banishment) and result.reason is R.UNBACKED_NUMBER


@CFG
@given(n=_NUM)
def test_p7_delimited_verified_quote_backs_token(n):
    token = repr(n)
    assume(token != "1")  # "1" is the cited line number, so it is backed anyway
    line = f"total {token} items"
    view = FakeView(files={"a.py": f"{line}\nother\n".encode()})
    cite = {"file": "a.py", "line_start": 1, "line_end": 1, "quote": line}
    delimited = {"text": f'It says "{line}"', "citations": [cite]}
    assert isinstance(verify_claim(view, delimited, 1, EMPTY), VerifiedClaim)
    bare = {"text": f"It says {line}", "citations": [cite]}
    result = verify_claim(view, bare, 1, EMPTY)
    assert isinstance(result, Banishment) and result.reason is R.UNBACKED_NUMBER


@CFG
@given(n=st.integers(0, 10**6))
def test_p7_snapshot_id_digits_back_token(n):
    sid = f"snap{n}abc"
    view = FakeView(files={"a.py": _FILE}, snapshot_id=sid)
    assert isinstance(verify_claim(view, _guess(f"At {sid} it works"), 1, EMPTY), VerifiedClaim)
