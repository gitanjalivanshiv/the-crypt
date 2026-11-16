import string

import pytest
from pydantic import ValidationError

from skeleton.verify.codes import MESSAGES, ReasonCode, render_message
from skeleton.verify.models import (
    AnswerResult,
    AttemptRecord,
    Banishment,
    Citation,
    CitationTarget,
    Figure,
    FigureTarget,
    NumberTarget,
    VerifiedClaim,
    VerifyConfig,
)


def test_enum_has_exactly_the_twelve_codes():
    assert {c.value for c in ReasonCode} == {
        "malformed", "path_unsafe", "file_not_found", "symlink",
        "range_invalid", "range_out_of_bounds", "file_unreadable",
        "quote_mismatch", "uncited_claim", "figure_not_in_metrics",
        "figure_not_cited", "unbacked_number",
    }  # fmt: skip


def test_messages_and_members_match_both_ways():
    assert set(MESSAGES) == set(ReasonCode)


@pytest.mark.parametrize("code", list(ReasonCode))
def test_messages_interpolate_only_the_failing_value(code):
    fields = [f for _, f, _, _ in string.Formatter().parse(MESSAGES[code]) if f]
    assert set(fields) <= {"value"}
    marker = "ZZ-MARKER"
    rendered = render_message(code, marker)
    assert ("{" not in rendered) and ("}" not in rendered)
    assert (marker in rendered) == bool(fields)


def _result() -> AnswerResult:
    cit = Citation(file="a.py", line_start=1, line_end=2, quote="x")
    fig = Figure(finding_id="churn:a.py:1-2", key="commit_count", value=847)
    ban = [
        Banishment(
            claim_text="c", reason=ReasonCode.QUOTE_MISMATCH,
            message=render_message(ReasonCode.QUOTE_MISMATCH, "a.py"),
            target=CitationTarget(index=0, citation=cit), attempt=1, snapshot_id="s",
        ),
        Banishment(
            claim_text="c", reason=ReasonCode.FIGURE_NOT_IN_METRICS, message="m",
            target=FigureTarget(index=0, figure=fig), attempt=1, snapshot_id="s",
        ),
        Banishment(
            claim_text="c", reason=ReasonCode.UNBACKED_NUMBER, message="m",
            target=NumberTarget(token="847"), attempt=2, snapshot_id="s",
        ),
        Banishment(
            claim_text="c", reason=ReasonCode.UNCITED_CLAIM, message="m",
            target=None, attempt=2, snapshot_id="s",
        ),
    ]  # fmt: skip
    return AnswerResult(
        snapshot_id="s",
        status="answered",
        claims=(VerifiedClaim(kind="fact", text="t", citations=(cit,), figures=(fig,)),),
        banishments=tuple(ban),
        attempts=(
            AttemptRecord(attempt=1, outcome="banished"),
            AttemptRecord(attempt=2, outcome="accepted"),
        ),
    )


def test_answer_result_round_trips_through_json():
    result = _result()
    assert AnswerResult.model_validate_json(result.model_dump_json()) == result


def test_models_are_frozen_and_reject_unknown_fields():
    cit = Citation(file="a.py", line_start=1, line_end=1)
    with pytest.raises(ValidationError):
        cit.file = "b.py"
    with pytest.raises(ValidationError):
        Citation(file="a.py", line_start=1, line_end=1, extra=1)
    with pytest.raises(ValidationError):
        VerifyConfig(bogus=1)
    with pytest.raises(ValidationError):
        AnswerResult(snapshot_id="s", status="declined", surprise=True)
    with pytest.raises(ValidationError):
        VerifiedClaim(kind="maybe", text="t")


def test_verify_config_allowed_numbers_defaults_empty():
    assert VerifyConfig().allowed_numbers == frozenset()
