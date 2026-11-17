"""Property tests for the grounded-turn flow (P8, P9)."""

import asyncio
import json

from hypothesis import given, settings
from hypothesis import strategies as st

from skeleton.verify.flow import run_grounded_turn
from skeleton.verify.models import VerifyConfig
from tests.verify.fake_view import FakeView

CFG = VerifyConfig()
GOOD = {"text": "good claim", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}
BAD = {"text": "bad claim", "citations": [{"file": "nope.py", "line_start": 1, "line_end": 1}]}

_OUTPUTS = {
    "good": json.dumps({"claims": [GOOD]}),
    "mixed": json.dumps({"claims": [GOOD, BAD]}),
    "bad": json.dumps({"claims": [BAD]}),
    "junk": "not json at all",
    "raises": RuntimeError("boom"),
}
behaviours = st.lists(st.sampled_from(sorted(_OUTPUTS)), min_size=1, max_size=3)


def _run(script: list[str]):
    calls: list[int] = []

    async def gen(attempt, feedback):
        calls.append(attempt)
        out = _OUTPUTS[script[min(len(calls), len(script)) - 1]]
        if isinstance(out, Exception):
            raise out
        return out

    view = FakeView(files={"a.py": b"x = 1\ny = 2\n"}, snapshot_id="snap-prop")
    result = asyncio.run(run_grounded_turn(view, gen, decline_line="no", cfg=CFG))
    return result, calls


@settings(max_examples=100, deadline=None)
@given(script=behaviours)
def test_p8_at_most_two_calls_and_snapshot_id(script):
    """**Validates: Requirements 4.14, 4.15**"""
    result, calls = _run(script)
    assert 1 <= len(calls) <= 2
    assert result.snapshot_id


@settings(max_examples=100, deadline=None)
@given(script=behaviours)
def test_p9_rejected_never_in_claims_and_declined_has_none(script):
    """**Validates: Requirements 4.16, 4.17**"""
    result, _ = _run(script)
    assert all(c.text != "bad claim" for c in result.claims)
    if result.status == "declined":
        assert result.claims == ()
