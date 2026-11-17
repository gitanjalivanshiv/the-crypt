"""Citation properties P2, P3, P4 (design 12.1).

**Validates: Requirements 4.22, 4.4, 4.6**
"""

import unicodedata

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from skeleton.verify.citation import CitationOk, Rejection, verify_citation
from skeleton.verify.codes import ReasonCode as R
from skeleton.verify.textnorm import split_lines
from tests.verify.fake_view import FakeView
from tests.verify.strategies import file_trees, valid_citation

CFG = settings(max_examples=200, deadline=None)


@st.composite
def tree_and_cite(draw):
    tree = draw(file_trees())
    return tree, draw(valid_citation(tree))


def _code(tree, raw):
    result = verify_citation(FakeView(files=tree.files), raw)
    return None if isinstance(result, CitationOk) else result.code


# ---- P2 -------------------------------------------------------------------


@CFG
@given(tc=tree_and_cite(), k=st.integers(1, 50))
def test_p2_end_past_eof_is_out_of_bounds(tc, k):
    tree, c = tc
    n = len(split_lines(tree.files[c["file"]]))
    assert _code(tree, {**c, "line_end": n + k}) is R.RANGE_OUT_OF_BOUNDS


@CFG
@given(tc=tree_and_cite())
def test_p2_start_after_end_is_range_invalid(tc):
    tree, c = tc
    assert _code(tree, {**c, "line_start": c["line_end"] + 1}) is R.RANGE_INVALID


@CFG
@given(tc=tree_and_cite(), s=st.integers(-1000, 0))
def test_p2_start_zero_or_negative_is_range_invalid(tc, s):
    tree, c = tc
    assert _code(tree, {**c, "line_start": s}) is R.RANGE_INVALID


@CFG
@given(tc=tree_and_cite(), data=st.data())
def test_p2_one_char_quote_change_is_mismatch(tc, data):
    tree, c = tc
    quote = c["quote"]
    positions = [i for i, ch in enumerate(quote) if ch != "\n"]
    assume(positions)
    i = data.draw(st.sampled_from(positions))
    repl = data.draw(st.sampled_from(["X", "Y", " ", "\u00e9", "\u0430"]))
    assume(repl != quote[i])
    mutated = quote[:i] + repl + quote[i + 1 :]
    assert _code(tree, {**c, "quote": mutated}) is R.QUOTE_MISMATCH


@CFG
@given(tc=tree_and_cite(), name=st.sampled_from(["nope.txt", "d0/missing.txt", "zz/yy/x.py"]))
def test_p2_unknown_file_is_not_found(tc, name):
    tree, c = tc
    assume(name not in tree.files)
    assert _code(tree, {**c, "file": name}) is R.FILE_NOT_FOUND


# ---- P3 -------------------------------------------------------------------

_SURR = st.text(alphabet=st.characters(min_codepoint=0xD800, max_codepoint=0xDFFF), max_size=4)
_STR = st.one_of(st.text(max_size=12), _SURR, st.sampled_from(["a.py", "../x", "/etc", "a\x00b", "C:x"]))
_JSON = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.floats(), _STR),
    lambda inner: st.one_of(
        st.lists(inner, max_size=4),
        st.dictionaries(_STR, inner, max_size=4),
    ),
    max_leaves=12,
)
_KEYED = st.fixed_dictionaries(
    {"line_start": _JSON, "line_end": _JSON},
    optional={"file": _JSON, "quote": _JSON},
)


@CFG
@given(raw=st.one_of(_JSON, _KEYED))
def test_p3_never_raises(raw):
    view = FakeView(files={"a.py": b"one\ntwo\n", "x": b"\xff\xfe\n"})
    result = verify_citation(view, raw)
    assert isinstance(result, (CitationOk, Rejection))


@CFG
@given(
    s=st.integers(-(2**70), 2**70),
    e=st.integers(-(2**70), 2**70),
    q=st.one_of(st.none(), _STR),
    f=st.sampled_from(["a.py", "x", "nope"]),
)
def test_p3_never_raises_keyed_ints(s, e, q, f):
    view = FakeView(files={"a.py": b"one\ntwo\n", "x": b"\xff\xfe\n"})
    result = verify_citation(view, {"file": f, "line_start": s, "line_end": e, "quote": q})
    assert isinstance(result, (CitationOk, Rejection))


# ---- P4 -------------------------------------------------------------------

_TERM = st.sampled_from(["\n", "\r\n", "\r"])
_WS = st.text(alphabet=" \t\f\v", max_size=3)


@st.composite
def _pieces(draw, lines, trailing=False):
    """Join lines with random terminators and trailing whitespace.

    A bare "\r" is never emitted before an empty piece, so adjacent
    terminators can never merge into a single "\r\n".
    """
    pieces = [ln + draw(_WS) for ln in lines]
    out = []
    for i, piece in enumerate(pieces):
        out.append(piece)
        if i < len(pieces) - 1 or trailing:
            nxt_empty = i + 1 < len(pieces) and piece_is_empty(pieces[i + 1])
            if i + 1 == len(pieces):
                nxt_empty = False
            out.append(draw(st.sampled_from(["\n", "\r\n"]) if nxt_empty else _TERM))
    return "".join(out)


def piece_is_empty(piece):
    return piece == ""


@CFG
@given(tc=tree_and_cite(), data=st.data())
def test_p4_terminator_and_trailing_ws_do_not_change_verdict(tc, data):
    tree, c = tc
    # By design (section 3), a quote whose last line is empty never matches.
    assume(c["quote"].split("\n")[-1] != "")
    path = c["file"]
    file_lines = [b.decode("utf-8") for b in split_lines(tree.files[path])]
    new_file = data.draw(_pieces(file_lines, trailing=True))
    files = {**tree.files, path: new_file.encode("utf-8")}
    quote = data.draw(_pieces(c["quote"].split("\n")))
    view = FakeView(files=files)
    assert isinstance(verify_citation(view, {**c, "quote": quote}), CitationOk)


@st.composite
def _single_line(draw):
    tree = draw(file_trees())
    c = draw(valid_citation(tree))
    lines = c["quote"].split("\n")
    idx = draw(st.integers(0, len(lines) - 1))
    return tree, c, lines, idx


def _flips(tree, c, lines, idx, new_line):
    mutated = lines[:idx] + [new_line] + lines[idx + 1 :]
    return _code(tree, {**c, "quote": "\n".join(mutated)}) is R.QUOTE_MISMATCH


@CFG
@given(x=_single_line())
def test_p4_leading_whitespace_flips(x):
    tree, c, lines, i = x
    assume(lines[i] != "")
    assert _flips(tree, c, lines, i, " " + lines[i])


@CFG
@given(x=_single_line())
def test_p4_interior_whitespace_flips(x):
    tree, c, lines, i = x
    assume(len(lines[i]) >= 2)
    assert _flips(tree, c, lines, i, lines[i][:1] + " " + lines[i][1:])


@CFG
@given(x=_single_line())
def test_p4_case_change_flips(x):
    tree, c, lines, i = x
    swapped = lines[i].swapcase()
    assume(swapped != lines[i])
    assert _flips(tree, c, lines, i, swapped)


@CFG
@given(x=_single_line())
def test_p4_unicode_normal_form_flips(x):
    tree, c, lines, i = x
    t = lines[i]
    alt = next((f for f in (unicodedata.normalize("NFD", t), unicodedata.normalize("NFC", t)) if f != t), None)
    assume(alt is not None)
    assert _flips(tree, c, lines, i, alt)
