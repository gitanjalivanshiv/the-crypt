"""The demo harness must stay coupled to the real retry wording.

demo/banishment.py decides whether to fabricate or ground by matching the prompt against
RETRY_MARKERS, which duplicates skeleton.personas.generator.render_feedback. If that
wording ever changes, the harness silently fabricates on every attempt: the turn declines
instead of recovering, no exception is raised, and the banishment shot in the video breaks
with no warning. These tests fail loudly instead.
"""

import asyncio
import importlib
import json

from skeleton.personas.generator import render_feedback
from skeleton.personas.llm import LLMRequest, Message
from skeleton.verify.codes import ReasonCode
from skeleton.verify.flow import AttemptFailure
from skeleton.verify.models import Banishment

banishment = importlib.import_module("demo.banishment")

BANISHED = Banishment(
    claim_text="It never existed.",
    reason=ReasonCode.FILE_NOT_FOUND,
    message="File not found: nope.py",
    attempt=1,
    snapshot_id="deadbeef",
)


def _request(*contents: str) -> LLMRequest:
    return LLMRequest(
        system="s", messages=tuple(Message(role="user", content=c) for c in contents)
    )


def _complete(client: object, request: LLMRequest) -> dict:
    response = asyncio.run(client.complete(request))  # type: ignore[attr-defined]
    return json.loads(response.text)["claims"][0]


def test_markers_match_real_banishment_feedback() -> None:
    assert render_feedback([BANISHED]).startswith(banishment.RETRY_MARKERS)


def test_markers_match_real_failure_feedback() -> None:
    failure = AttemptFailure(kind="generator_error", detail="boom")
    assert render_feedback(failure).startswith(banishment.RETRY_MARKERS)


def test_first_attempt_fabricates_an_unresolvable_citation() -> None:
    claim = _complete(banishment.ScriptedGhost(), _request("Why?"))
    assert claim == banishment.FABRICATED


def test_retry_grounds() -> None:
    ghost = banishment.ScriptedGhost()
    _complete(ghost, _request("Why?"))
    claim = _complete(ghost, _request("Why?", render_feedback([BANISHED])))
    assert claim == banishment.GROUNDED
    assert (ghost.fabricated, ghost.grounded) == (1, 1)


def test_every_turn_banishes_then_grounds() -> None:
    """FakeLLMClient replays a fixed list and raises once exhausted, so it dies after one
    turn in a UI session. This client is keyed on the request, so it does not."""
    ghost = banishment.ScriptedGhost()
    for _ in range(3):
        assert _complete(ghost, _request("Q")) == banishment.FABRICATED
        assert _complete(ghost, _request("Q", render_feedback([BANISHED]))) == banishment.GROUNDED
    assert (ghost.fabricated, ghost.grounded) == (3, 3)


def test_claims_carry_no_digits() -> None:
    """A figure must be backed by Finding.metrics or the verifier banishes it as
    unbacked_number, which would bury the reason code the demo exists to show."""
    for claim in (banishment.FABRICATED, banishment.GROUNDED):
        assert not any(ch.isdigit() for ch in str(claim["text"]))
