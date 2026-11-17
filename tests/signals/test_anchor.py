from skeleton.ingest.parse import parse_python
from skeleton.signals.anchor import anchor_range


def anchor(src: str) -> tuple[int, int] | None:
    data = src.encode()
    return anchor_range(data, parse_python(data))


def test_docstring_range_wins() -> None:
    assert anchor('"""Doc\nmore\n"""\n\ndef f():\n    pass\n') == (1, 3)


def test_first_definition_capped_at_three_lines() -> None:
    src = "import os\n\ndef f():\n    a = 1\n    b = 2\n    c = 3\n"
    assert anchor(src) == (3, 5)


def test_short_definition_not_extended() -> None:
    assert anchor("x = 1\nclass A: pass\ny = 2\n") == (2, 2)


def test_first_lines_fallback() -> None:
    assert anchor("a = 1\nb = 2\nc = 3\nd = 4\n") == (1, 3)
    assert anchor("a = 1\n") == (1, 1)


def test_docstring_only_file() -> None:
    assert anchor('"""Only doc."""\n') == (1, 1)


def test_syntax_error_file_still_anchors() -> None:
    result = anchor("def (:\n  ??\n")
    assert result is not None
    assert 1 <= result[0] <= result[1] <= 2


def test_empty_file_is_none() -> None:
    assert anchor("") is None
