import pytest

from skeleton.verify.citation import CitationOk, Rejection, verify_citation
from skeleton.verify.codes import ReasonCode
from tests.verify.fake_view import FakeView, RealDirView

THREE = b"one\ntwo\nthree\n"


def view(**files: bytes) -> FakeView:
    return FakeView(files={"a.py": THREE, "empty.py": b"", "bin.py": b"\xff\xfe\n", **files})


def cite(file="a.py", s=1, e=1, **extra):
    return {"file": file, "line_start": s, "line_end": e, **extra}


def code(result) -> ReasonCode:
    assert isinstance(result, Rejection)
    return result.code


def test_valid_without_quote():
    r = verify_citation(view(), cite(s=1, e=3))
    assert isinstance(r, CitationOk)
    assert r.citation.quote is None


def test_valid_with_quote_and_trailing_whitespace():
    r = verify_citation(view(), cite(s=2, e=3, quote="two  \nthree\t"))
    assert isinstance(r, CitationOk)
    assert r.citation.quote == "two  \nthree\t"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "x",
        [],
        {"line_start": 1, "line_end": 1},
        cite(file=3),
        cite(s="1"),
        cite(e=1.0),
        cite(quote=5),
    ],
)
def test_malformed(raw):
    assert code(verify_citation(view(), raw)) is ReasonCode.MALFORMED


@pytest.mark.parametrize("which", ["s", "e"])
def test_true_line_number_is_malformed(which):
    raw = cite(s=True) if which == "s" else cite(e=True)
    assert code(verify_citation(view(), raw)) is ReasonCode.MALFORMED


@pytest.mark.parametrize(
    "path",
    ["", "/etc/passwd", "a/../b", "..", "a\x00b", "a\\b", "C:foo", "bad\ud800"],
)
def test_path_unsafe(path):
    assert code(verify_citation(view(), cite(file=path))) is ReasonCode.PATH_UNSAFE


def test_dotdot_inside_a_name_is_safe():
    v = view(**{"a..b.py": b"x\n"})
    assert isinstance(verify_citation(v, cite(file="a..b.py")), CitationOk)


def test_symlink_file():
    v = FakeView(files={"real.py": b"x\n"}, symlinks={"link.py": "real.py"})
    assert code(verify_citation(v, cite(file="link.py"))) is ReasonCode.SYMLINK


def test_file_not_found_missing():
    assert code(verify_citation(view(), cite(file="nope.py"))) is ReasonCode.FILE_NOT_FOUND


def test_file_not_found_when_bytes_unreadable():
    class NoBytes(FakeView):
        def read_bytes(self, path):
            return None

    v = NoBytes(files={"a.py": THREE})
    assert code(verify_citation(v, cite())) is ReasonCode.FILE_NOT_FOUND


def test_d1_symlinked_directory_reports_symlink_not_file_not_found():
    v = FakeView(files={"real/a.py": b"x\n"}, symlink_dirs={"linkdir": "real"})
    assert code(verify_citation(v, cite(file="linkdir/a.py"))) is ReasonCode.SYMLINK


def test_d1_symlinked_directory_on_real_filesystem(tmp_path):
    v = RealDirView(tmp_path, files={"real/a.py": b"x\n"}, symlink_dirs={"linkdir": "real"})
    assert code(verify_citation(v, cite(file="linkdir/a.py"))) is ReasonCode.SYMLINK
    assert isinstance(verify_citation(v, cite(file="real/a.py")), CitationOk)


@pytest.mark.parametrize("s,e", [(0, 1), (-1, 2), (5, 2)])
def test_range_invalid(s, e):
    assert code(verify_citation(view(), cite(s=s, e=e))) is ReasonCode.RANGE_INVALID


def test_reversed_range_on_three_line_file_is_invalid_not_out_of_bounds():
    assert code(verify_citation(view(), cite(s=5, e=2))) is ReasonCode.RANGE_INVALID


def test_range_out_of_bounds():
    assert code(verify_citation(view(), cite(s=1, e=4))) is ReasonCode.RANGE_OUT_OF_BOUNDS


@pytest.mark.parametrize("s,e", [(1, 1), (1, 5), (3, 3), (2, 9)])
def test_every_valid_range_on_empty_file_is_out_of_bounds(s, e):
    r = verify_citation(view(), cite(file="empty.py", s=s, e=e))
    assert code(r) is ReasonCode.RANGE_OUT_OF_BOUNDS


def test_file_unreadable_with_quote():
    r = verify_citation(view(), cite(file="bin.py", quote="x"))
    assert code(r) is ReasonCode.FILE_UNREADABLE


@pytest.mark.parametrize("quote_key", [True, False])
def test_non_utf8_file_without_quote_is_valid(quote_key):
    raw = cite(file="bin.py", quote=None) if quote_key else cite(file="bin.py")
    assert isinstance(verify_citation(view(), raw), CitationOk)


def test_genuine_replacement_char_is_valid_utf8():
    v = view(**{"u.py": "a\ufffd\n".encode()})
    assert isinstance(verify_citation(v, cite(file="u.py", quote="a\ufffd")), CitationOk)


@pytest.mark.parametrize("quote", ["TWO", "  two", "tw o", "one", "", "\ud800"])
def test_quote_mismatch(quote):
    r = verify_citation(view(), cite(s=2, e=2, quote=quote))
    assert code(r) is ReasonCode.QUOTE_MISMATCH


def test_quote_unicode_form_is_not_normalised():
    v = view(**{"u.py": "caf\u00e9\n".encode()})
    r = verify_citation(v, cite(file="u.py", quote="cafe\u0301"))
    assert code(r) is ReasonCode.QUOTE_MISMATCH


def test_crlf_quote_against_lf_file_passes():
    r = verify_citation(view(), cite(s=1, e=2, quote="one\r\ntwo"))
    assert isinstance(r, CitationOk)


def test_quote_null_and_missing_quote_both_mean_no_quote():
    a = verify_citation(view(), cite(quote=None))
    b = verify_citation(view(), cite())
    assert isinstance(a, CitationOk) and isinstance(b, CitationOk)
    assert a.citation == b.citation


def test_extra_keys_are_ignored():
    r = verify_citation(view(), cite(extra="x", other=[1]))
    assert isinstance(r, CitationOk)


def test_rejection_message_uses_fixed_template():
    r = verify_citation(view(), cite(file="nope.py"))
    assert isinstance(r, Rejection)
    assert r.message == "File not found: nope.py"
