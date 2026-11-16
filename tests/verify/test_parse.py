import json

import pytest

from skeleton.verify.parse import ParseFailure, parse_answer

ITEM = {"kind": "fact", "text": "x"}
RAW = json.dumps({"claims": [ITEM]})


def test_unfenced():
    assert parse_answer(RAW) == [ITEM]


@pytest.mark.parametrize("fence", ["```", "```json"])
def test_fenced(fence):
    assert parse_answer(f"{fence}\n{RAW}\n```") == [ITEM]


def test_fence_without_newline():
    assert parse_answer(f"```{RAW}```") == [ITEM]


def test_trailing_prose_fails():
    assert isinstance(parse_answer(RAW + "\nHope this helps"), ParseFailure)


def test_nested_fence_inside_string_survives():
    inner = {"claims": [{"text": "a ```b``` c"}]}
    assert parse_answer(f"```json\n{json.dumps(inner)}\n```") == inner["claims"]


def test_double_fence_fails():
    assert isinstance(parse_answer(f"```\n```json\n{RAW}\n```\n```"), ParseFailure)


@pytest.mark.parametrize(
    "text",
    ["", "nope", "[1]", '"s"', "{}", '{"claims": {}}', '{"claims": "x"}', '{"claims": []}'],
)
def test_failures(text):
    r = parse_answer(text)
    assert isinstance(r, ParseFailure)
    assert "ParseFailure" in repr(r)


def test_non_dict_items_preserved():
    items = [ITEM, 5, "s", None, [1]]
    assert parse_answer(json.dumps({"claims": items})) == items


def test_deep_nesting_never_raises():
    assert isinstance(parse_answer("[" * 100000), ParseFailure)
