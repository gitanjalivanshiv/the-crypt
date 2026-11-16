"""Citation fuzz table (design 12.2, R4.23). One named case per hostile input."""

import pytest

from skeleton.verify.citation import CitationOk, verify_citation
from skeleton.verify.codes import ReasonCode as R
from tests.verify.fake_view import FakeView, RealDirView

N = 3
FILE = b"one\ntwo\nthree\n"
NFC = "caf\u00e9"
NFD = "cafe\u0301"


def cite(file="a.py", s=1, e=1, **extra):
    return {"file": file, "line_start": s, "line_end": e, **extra}


def _fake():
    return FakeView(
        files={
            "a.py": FILE,
            "empty.py": b"",
            "crlf.py": b"one\r\ntwo\r\nthree\r\n",
            "cr.py": b"one\rtwo\rthree\r",
            "nfc.py": (NFC + "\n").encode(),
            "cyr.py": b"pace\n",
        }
    )


def _real(tmp_path):
    return RealDirView(
        tmp_path,
        files={"a.py": FILE, "real/x.py": FILE},
        symlinks={"flink.py": "a.py", "dangling.py": "nowhere.py"},
        symlink_dirs={"dlink": "real"},
    )


# (id, builder kind, raw citation, expected code or None for acceptance)
CASES = [
    ("fabricated_path", "fake", cite("no/such.py"), R.FILE_NOT_FOUND),
    ("dotdot_etc_passwd", "fake", cite("../etc/passwd"), R.PATH_UNSAFE),
    ("embedded_dotdot", "fake", cite("a/../b"), R.PATH_UNSAFE),
    ("absolute_path", "fake", cite("/etc/passwd"), R.PATH_UNSAFE),
    ("windows_drive", "fake", cite("C:\\x"), R.PATH_UNSAFE),
    ("nul_byte", "fake", cite("a\x00.py"), R.PATH_UNSAFE),
    ("backslash", "fake", cite("dir\\a.py"), R.PATH_UNSAFE),
    ("file_symlink", "real", cite("flink.py"), R.SYMLINK),
    ("dir_symlink_ancestor", "real", cite("dlink/x.py"), R.SYMLINK),
    ("dangling_symlink", "real", cite("dangling.py"), R.SYMLINK),
    ("range_0_1", "fake", cite(s=0, e=1), R.RANGE_INVALID),
    ("range_3_2", "fake", cite(s=3, e=2), R.RANGE_INVALID),
    ("range_1_n_plus_1", "fake", cite(s=1, e=N + 1), R.RANGE_OUT_OF_BOUNDS),
    ("range_n_n_accepted", "fake", cite(s=N, e=N), None),
    ("range_n1_n1", "fake", cite(s=N + 1, e=N + 1), R.RANGE_OUT_OF_BOUNDS),
    ("quote_one_char_changed", "fake", cite(s=1, e=1, quote="onf"), R.QUOTE_MISMATCH),
    ("quote_leading_space", "fake", cite(s=1, e=1, quote=" one"), R.QUOTE_MISMATCH),
    ("quote_nfd_vs_nfc_file", "fake", cite("nfc.py", quote=NFD), R.QUOTE_MISMATCH),
    ("cyrillic_homoglyph", "fake", cite("cyr.py", quote="p\u0430ce"), R.QUOTE_MISMATCH),
    ("crlf_file_accepted", "fake", cite("crlf.py", 1, 3, quote="one\ntwo\nthree"), None),
    ("lone_cr_file_accepted", "fake", cite("cr.py", 1, 3, quote="one\ntwo\nthree"), None),
    ("crlf_quote_accepted", "fake", cite(s=1, e=2, quote="one\r\ntwo"), None),
    ("lone_cr_quote_accepted", "fake", cite(s=1, e=2, quote="one\rtwo"), None),
    ("empty_file", "fake", cite("empty.py", 1, 1), R.RANGE_OUT_OF_BOUNDS),
    ("true_as_line_number", "fake", cite(s=True, e=1), R.MALFORMED),
    ("missing_file_key", "fake", {"line_start": 1, "line_end": 1}, R.MALFORMED),
    ("quote_is_int", "fake", cite(quote=123), R.MALFORMED),
]


@pytest.mark.parametrize(
    "kind,raw,expected", [pytest.param(k, r, x, id=i) for i, k, r, x in CASES]
)
def test_citation_fuzz(kind, raw, expected, tmp_path):
    view = _real(tmp_path) if kind == "real" else _fake()
    result = verify_citation(view, raw)
    if expected is None:
        assert isinstance(result, CitationOk)
    else:
        assert not isinstance(result, CitationOk)
        assert result.code is expected
