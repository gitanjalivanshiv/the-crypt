"""The fixed question set (medium R3.1 to R3.3)."""
import re
import tomllib
from collections import Counter
from pathlib import Path

from medium.plan import SECTION_QUESTIONS

PATH = Path(__file__).resolve().parents[2] / "medium" / "eval" / "questions.toml"
QUESTIONS = tomllib.loads(PATH.read_text())["questions"]

# Churn and staleness together form one minimum of 4.
MINIMUMS = {"exact_number": 4, "todo": 3, "named_file": 3, "unanswerable": 3, "plan": 3}
PEOPLE_WORDS = re.compile(
    r"\b(who|whose|whom|author|authors|maintainer|maintainers|developer|developers|"
    r"blame|blamed|fault|lazy|negligent|careless|contributor|contributors|committer)\b",
    re.IGNORECASE,
)


def test_exactly_twenty_questions():
    assert len(QUESTIONS) == 20


def test_ids_unique_and_fields_present():
    ids = [q["id"] for q in QUESTIONS]
    assert len(set(ids)) == len(ids)
    assert all(q["id"] and q["category"] for q in QUESTIONS)


def test_category_minimums():
    counts = Counter(q["category"] for q in QUESTIONS)
    for category, minimum in MINIMUMS.items():
        assert counts[category] >= minimum, category
    assert counts["churn"] + counts["staleness"] >= 4


def test_plan_ids_resolve():
    plan = [q["id"] for q in QUESTIONS if q["category"] == "plan"]
    assert sorted(plan) == sorted(f"plan:{s}" for s in SECTION_QUESTIONS)
    for q in QUESTIONS:
        if q["category"] == "plan":
            assert "text" not in q  # wording has one source


def test_non_plan_questions_have_text():
    for q in QUESTIONS:
        if q["category"] != "plan":
            assert q.get("text", "").strip(), q["id"]


def test_no_questions_about_people():
    for q in QUESTIONS:
        assert not PEOPLE_WORDS.search(q.get("text", "")), q["id"]


def test_sha_recorded_in_comment():
    assert "049ae8e3083514378aedb352a2017fbc306bd126" in PATH.read_text()
