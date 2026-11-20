"""Resurrection plan questions and models (medium R6)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from skeleton.verify.models import AnswerResult

SECTIONS = ("requirements", "design", "tasks")

# Each question stands alone: no digits, no mention of another section or its output.
SECTION_QUESTIONS: dict[str, str] = {
    "requirements": (
        "Haunted by the passing of time, what must this system still do for its users "
        "before it can be modernised? Name each modernisation step you would take to "
        "preserve that behaviour, and cite the code that shows it."
    ),
    "design": (
        "The old structure creaks under the weight of the years. What shape should the "
        "modernised system take? Name each modernisation step needed to get there from "
        "the current code, and cite the code each step touches."
    ),
    "tasks": (
        "Which pieces of this ageing code should be raised from the grave first? List "
        "the modernisation steps in a sensible order, each tied to code you can cite."
    ),
}


class PlanSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: Literal["requirements", "design", "tasks"]
    result: AnswerResult


class PlanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    sections: tuple[PlanSection, ...]
