import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from skeleton.verify.textnorm import (
    normalise_line,
    normalise_quote,
    normalised_lines,
    split_lines,
)


def test_empty_is_zero_lines():
    assert split_lines(b"") == []
    assert normalised_lines(b"") == []
    assert normalise_quote("") == []


def test_single_trailing_terminator_adds_no_line():
    assert split_lines(b"x\n") == [b"x"]
    assert normalise_quote("x\n") == ["x"]
    assert split_lines(b"x\n\n") == [b"x", b""]


@pytest.mark.parametrize("term", [b"\r\n", b"\r", b"\n"])
def test_each_terminator_splits_once(term):
    assert split_lines(b"a" + term + b"b") == [b"a", b"b"]


@pytest.mark.parametrize("sep", ["\u2028", "\x0b", "\x0c", "\x85"])
def test_other_separators_do_not_split(sep):
    assert len(normalised_lines(f"a{sep}b".encode())) == 1


def test_only_trailing_ascii_whitespace_stripped():
    assert normalise_line("a \t\f\v") == "a"
    assert normalise_line("a\u00a0") == "a\u00a0"
    assert normalise_line("  a") == "  a"


def test_unicode_forms_not_normalised():
    nfc = unicodedata.normalize("NFC", "é")
    nfd = unicodedata.normalize("NFD", "é")
    assert normalise_quote(nfc) != normalise_quote(nfd)


def test_invalid_utf8_still_counts_lines():
    data = b"a\xff\nb\r\nc"
    assert len(split_lines(data)) == 3
    with pytest.raises(UnicodeDecodeError):
        normalised_lines(data)


_line = st.text(
    alphabet=st.characters(blacklist_characters="\r\n", blacklist_categories=("Cs",)),
    max_size=20,
)


@given(
    lines=st.lists(_line, max_size=8),
    term=st.sampled_from(["\n", "\r\n", "\r"]),
    pad=st.text(alphabet=" \t\f\v", max_size=4),
    trailing=st.booleans(),
)
def test_p5_terminator_and_trailing_whitespace_invariance(lines, term, pad, trailing):
    """**Validates: Requirements 4.4, 4.2**"""
    # An unterminated empty last line is indistinguishable from no line, so only
    # drop the final terminator when the last line is non-empty.
    terminated = trailing or not lines or lines[-1] == ""
    base = "\n".join(lines) + ("\n" if terminated and lines else "")
    variant = term.join(line + pad for line in lines) + (term if terminated and lines else "")
    assert normalised_lines(variant.encode()) == normalised_lines(base.encode())
    assert normalise_quote(variant) == normalised_lines(variant.encode())
    assert len(normalised_lines(base.encode())) == len(lines)
