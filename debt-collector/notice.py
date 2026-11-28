"""The notice question: one constant template, one variable (the level word)."""

from .interest import LEVELS

NOTICE_TEMPLATE = (
    "Issue a {level} notice on the accounts of this codebase. Itemise the largest debts, "
    "one claim for each, and cite the code that shows each one. Match the register of a "
    "{level} notice. Use only figures that the findings supply."
)


def notice_question(level: str) -> str:
    """Question for the skeleton's /ask. Depends only on the level word; has no digit."""
    if level not in LEVELS:
        raise ValueError(f"unknown escalation level {level!r}; known: {list(LEVELS)}")
    return NOTICE_TEMPLATE.format(level=level)
