import asyncio
import json

from skeleton.verify.codes import ReasonCode
from skeleton.verify.flow import AttemptFailure, run_grounded_turn
from skeleton.verify.models import Banishment, VerifyConfig
from tests.verify.fake_view import FakeView

CFG = VerifyConfig()
DECLINE = "I cannot answer that."
GOOD = {"text": "good one", "citations": [{"file": "a.py", "line_start": 1, "line_end": 1}]}
GOOD2 = {"text": "good two", "citations": [{"file": "a.py", "line_start": 2, "line_end": 2}]}
BAD = {"text": "bad one", "citations": [{"file": "nope.py", "line_start": 1, "line_end": 1}]}


def view() -> FakeView:
    return FakeView(files={"a.py": b"x = 1\ny = 2\n"}, snapshot_id="snap-1")


def answer(*claims: object) -> str:
    return json.dumps({"claims": list(claims)})


class Script:
    """Generator returning (or raising) scripted outputs; records calls."""

    def __init__(self, *outputs: object) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[int, object]] = []

    async def __call__(self, attempt, feedback):
        self.calls.append((attempt, feedback))
        out = self.outputs[min(len(self.calls), len(self.outputs)) - 1]
        if isinstance(out, Exception):
            raise out
        return out


def run(gen: Script):
    return asyncio.run(run_grounded_turn(view(), gen, decline_line=DECLINE, cfg=CFG))


def test_first_try_success():
    gen = Script(answer(GOOD, GOOD2))
    r = run(gen)
    assert r.status == "answered" and len(r.claims) == 2
    assert r.banishments == () and r.decline_line is None
    assert r.snapshot_id == "snap-1"
    assert [a.outcome for a in r.attempts] == ["accepted"]
    assert len(gen.calls) == 1 and gen.calls[0] == (1, None)


def test_fail_then_succeed_keeps_attempt1_banishments_not_claims():
    gen = Script(answer(GOOD, BAD), answer(GOOD2))
    r = run(gen)
    assert r.status == "answered"
    assert [c.text for c in r.claims] == ["good two"]
    assert len(r.banishments) == 1
    assert r.banishments[0].reason == ReasonCode.FILE_NOT_FOUND
    assert r.banishments[0].attempt == 1
    assert [a.outcome for a in r.attempts] == ["banished", "accepted"]


def test_feedback_to_attempt_2_is_structured_banishments():
    gen = Script(answer(GOOD, BAD), answer(GOOD))
    r = run(gen)
    attempt, feedback = gen.calls[1]
    assert attempt == 2
    assert feedback == r.banishments
    assert all(isinstance(b, Banishment) for b in feedback)


def test_fail_then_fail_declines_with_all_banishments():
    gen = Script(answer(BAD), answer(GOOD, BAD))
    r = run(gen)
    assert r.status == "declined" and r.claims == ()
    assert r.decline_line == DECLINE and r.snapshot_id == "snap-1"
    assert [b.attempt for b in r.banishments] == [1, 2]
    assert [a.outcome for a in r.attempts] == ["banished", "banished"]


def test_always_failing_generator_called_at_most_twice():
    gen = Script(answer(BAD))
    r = run(gen)
    assert len(gen.calls) == 2 and r.status == "declined"


def test_generator_raises_both_times_declines():
    gen = Script(RuntimeError("boom"))
    r = run(gen)
    assert r.status == "declined" and r.banishments == () and r.claims == ()
    assert r.snapshot_id == "snap-1"
    assert [a.failure_kind for a in r.attempts] == ["generator_error"] * 2
    assert gen.calls[1][1] == AttemptFailure("generator_error", "RuntimeError")


def test_generator_raises_then_succeeds():
    r = run(Script(RuntimeError("boom"), answer(GOOD)))
    assert r.status == "answered" and len(r.claims) == 1
    assert r.attempts[0].outcome == "failed"


def test_junk_output_declines_and_passes_failure_feedback():
    gen = Script("not json at all")
    r = run(gen)
    assert r.status == "declined"
    assert [a.failure_kind for a in r.attempts] == ["unparseable"] * 2
    assert isinstance(gen.calls[1][1], AttemptFailure)
    assert gen.calls[1][1].kind == "unparseable"


def test_non_string_output_is_unparseable():
    r = run(Script(None, answer(GOOD)))
    assert r.status == "answered"
    assert r.attempts[0].failure_kind == "unparseable"


def test_non_dict_item_is_banished_without_discarding_others():
    r = run(Script(answer(GOOD, 42), answer(GOOD)))
    assert r.banishments[0].reason == ReasonCode.MALFORMED
    assert r.status == "answered" and len(r.claims) == 1


def test_attempt1_failure_then_attempt2_banished_declines():
    r = run(Script("junk", answer(BAD)))
    assert r.status == "declined"
    assert [b.attempt for b in r.banishments] == [2]
    assert [a.outcome for a in r.attempts] == ["failed", "banished"]
