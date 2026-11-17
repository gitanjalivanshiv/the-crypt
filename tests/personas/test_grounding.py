import json
import re

from skeleton.personas.grounding import GROUNDING, GROUNDING_REMINDER
from skeleton.verify.claim import verify_claim
from skeleton.verify.models import VerifiedClaim, VerifyConfig
from skeleton.verify.parse import ParseFailure, parse_answer
from tests.verify.fake_view import FakeView


def _example() -> str:
    m = re.search(r"```json\n(.*?)\n```", GROUNDING, re.S)
    assert m
    return m.group(1)


def _view() -> FakeView:
    return FakeView(
        files={"setup.py": b'from setuptools import setup\n\nsetup(name="demo")\n'},
        findings={"churn:setup.py:1-3": ("setup.py", {"commit_count": 412})},
        snapshot_id="snap-1",
    )


def test_example_parses():
    claims = parse_answer(_example())
    assert not isinstance(claims, ParseFailure)
    assert len(claims) == 1
    assert set(json.loads(_example())["claims"][0]) == {"text", "guess", "citations", "figures"}


def test_example_verifies_against_fixture_snapshot():
    claims = parse_answer(_example())
    assert not isinstance(claims, ParseFailure)
    result = verify_claim(_view(), claims[0], 1, VerifyConfig())
    assert isinstance(result, VerifiedClaim)
    assert result.figures[0].value == 412


def test_text_mentions_each_rule():
    for needle in (
        "`claims`",
        "line_start",
        "line_end",
        "quote",
        "guess",
        "finding_id",
        "figures",
        "backticks",
        "digits",
        "declined",
    ):
        assert needle in GROUNDING, needle
    assert "must not carry any `figures`" in GROUNDING


def test_reminder_mentions_core_rules():
    for needle in ("`claims`", "line_start", "guess", "finding_id", "backticks", "digits"):
        assert needle in GROUNDING_REMINDER, needle
