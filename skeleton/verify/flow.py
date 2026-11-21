"""Reject-and-regenerate-once flow (design §6.5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from skeleton.verify.claim import verify_claim
from skeleton.verify.models import (
    AnswerResult,
    AttemptRecord,
    Banishment,
    SnapshotView,
    VerifiedClaim,
    VerifyConfig,
)
from skeleton.verify.parse import ParseFailure, parse_answer

_DETAIL_MAX = 300


@dataclass(frozen=True)
class AttemptFailure:
    """Feedback for a regeneration when the previous attempt produced no claims."""

    kind: Literal["generator_error", "unparseable"]
    detail: str


class Generator(Protocol):
    async def __call__(
        self, attempt: int, feedback: Sequence[Banishment] | AttemptFailure | None
    ) -> str: ...


@dataclass(frozen=True)
class _Attempt:
    claims: tuple[VerifiedClaim, ...]
    banishments: tuple[Banishment, ...]
    failure: AttemptFailure | None


def classify_attempt(attempt: _Attempt) -> bool:
    """Return True when the attempt is acceptable.

    The single seam for the acceptance rule (watch item 1): an all-guess answer
    could be routed to the decline path here later.
    """
    return attempt.failure is None and not attempt.banishments


def _record(n: int, attempt: _Attempt) -> AttemptRecord:
    if attempt.failure is not None:
        return AttemptRecord(
            attempt=n,
            outcome="failed",
            failure_kind=attempt.failure.kind,
            failure_detail=attempt.failure.detail,
        )
    outcome = "banished" if attempt.banishments else "accepted"
    return AttemptRecord(attempt=n, outcome=outcome)


async def _attempt(
    view: SnapshotView,
    generate: Generator,
    n: int,
    feedback: Sequence[Banishment] | AttemptFailure | None,
    cfg: VerifyConfig,
) -> _Attempt:
    try:
        text = await generate(n, feedback)
    except Exception as exc:  # noqa: BLE001 - generator is untrusted; any failure fails the attempt
        detail = f"{type(exc).__name__}: {exc}"[:_DETAIL_MAX]
        return _Attempt((), (), AttemptFailure("generator_error", detail))
    items = parse_answer(text if isinstance(text, str) else "")
    if isinstance(items, ParseFailure):
        return _Attempt((), (), AttemptFailure("unparseable", items.reason))
    claims: list[VerifiedClaim] = []
    banished: list[Banishment] = []
    for item in items:
        result = verify_claim(view, item, n, cfg)
        if isinstance(result, Banishment):
            banished.append(result)
        else:
            claims.append(result)
    return _Attempt(tuple(claims), tuple(banished), None)


async def run_grounded_turn(
    view: SnapshotView,
    generate: Generator,
    *,
    decline_line: str,
    cfg: VerifyConfig,
) -> AnswerResult:
    """Run at most two attempts. Never raises from generator or model output."""
    first = await _attempt(view, generate, 1, None, cfg)
    records = [_record(1, first)]
    if classify_attempt(first):
        return AnswerResult(
            snapshot_id=view.snapshot_id,
            status="answered",
            claims=first.claims,
            attempts=tuple(records),
        )

    feedback = first.banishments if first.banishments else first.failure
    second = await _attempt(view, generate, 2, feedback, cfg)
    records.append(_record(2, second))
    if classify_attempt(second):
        return AnswerResult(
            snapshot_id=view.snapshot_id,
            status="answered",
            claims=second.claims,
            banishments=first.banishments,
            attempts=tuple(records),
        )
    return AnswerResult(
        snapshot_id=view.snapshot_id,
        status="declined",
        claims=(),
        banishments=first.banishments + second.banishments,
        decline_line=decline_line,
        attempts=tuple(records),
    )
