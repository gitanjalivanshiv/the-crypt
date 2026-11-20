"""Plan section questions and models (medium R6.1, R6.4, R6.8)."""
import re

from medium.plan import SECTION_QUESTIONS, SECTIONS, PlanResult, PlanSection
from skeleton.verify.models import (
    AnswerResult,
    Citation,
    VerifiedClaim,
)


def test_three_sections_in_fixed_order() -> None:
    assert SECTIONS == ("requirements", "design", "tasks")
    assert tuple(SECTION_QUESTIONS) == SECTIONS


def test_no_digit_in_any_question() -> None:
    for question in SECTION_QUESTIONS.values():
        assert not re.search(r"\d", question)


def test_questions_are_independent() -> None:
    for section, question in SECTION_QUESTIONS.items():
        lowered = question.lower()
        for other in SECTIONS:
            assert other not in lowered, (section, other)
        for other_section, other_question in SECTION_QUESTIONS.items():
            if other_section != section:
                assert other_question not in question


def test_models_round_trip_answer_result_unchanged() -> None:
    result = AnswerResult(
        snapshot_id="snap",
        status="answered",
        claims=(
            VerifiedClaim(
                kind="fact",
                text="It creaks.",
                citations=(Citation(file="a.py", line_start=1, line_end=2),),
            ),
        ),
    )
    plan = PlanResult(
        snapshot_id="snap",
        sections=tuple(PlanSection(section=s, result=result) for s in SECTIONS),
    )
    assert all(s.result is result or s.result == result for s in plan.sections)
    assert PlanResult.model_validate(plan.model_dump()) == plan
    assert PlanResult.model_validate_json(plan.model_dump_json()) == plan
