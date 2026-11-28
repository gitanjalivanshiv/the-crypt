"""Interest: the pure arithmetic of the Debt Collector.

Every number the collector shows is a ``Finding.metrics`` value or a value named
in ``FIGURES``. Nothing here reads a clock, a random source, a file, the network
or a model. The formula reads severity and the line range, never a metric by
name (design D2): severity is already the analyzer's function of its metrics.
"""

import math
from collections.abc import Iterable, Sequence
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict

from skeleton.signals.models import Finding

# Every output is rounded to this many places (R1.2). Rounding is monotone, so
# the monotonicity of interest in severity survives it.
PLACES = 6

# Exponent on severity. Convex on purpose: a finding at 0.9 costs four times one
# at 0.45, so the few worst debts stand out and "boss" lines are real. A linear
# rate would flatten the ledger. With severity in [0, 1] the rate stays in
# [0, 1], so interest never exceeds principal.
SEVERITY_EXPONENT = 2

# Effort is 1 + log2(1 + principal): a 40-line range is more work than a 4-line
# one, but not ten times more. Because effort differs from principal, the plan's
# order differs from the ledger's: short, severe debts come first.
EFFORT_BASE = 1.0

# How many of the highest-interest lines are flagged boss (R1.8). Three is few
# enough to feel like a boss and enough to fill a screen of targets.
BOSS_COUNT = 3

# Escalation words, mildest first (R4.2). The persona must describe each one.
LEVELS: tuple[str, ...] = ("courtesy", "reminder", "demand", "final")

# The level is the last entry whose cut-off the total severity reaches. Starting
# values, to be tuned once by hand against the patient's real ledger. Each is a
# sum of severities (each in [0, 1]), so 3.0 is "a few notable debts", 15.0 is
# "a file-wide problem" and 40.0 is "the codebase is in arrears".
ESCALATION_CUTOFFS: tuple[tuple[str, float], ...] = (
    ("courtesy", 0.0),
    ("reminder", 3.0),
    ("demand", 15.0),
    ("final", 40.0),
)

Level = Literal["courtesy", "reminder", "demand", "final"]

UNSPECIFIED_UNIT = "unspecified"

# Unit of every metric key the shipped analyzers emit (R1.4). A test reads the
# analyzers' source and fails if a key is missing here.
METRIC_UNITS: dict[str, str] = {
    "commit_count": "commits (all time, up to the snapshot's pinned commit)",
    "author_count": "distinct authors",
    "days_since_modified": "days",
    "age_days": "days",
    "todo_count_in_file": "markers in the file",
}


def metric_unit(key: str) -> str:
    """Unit of a metric key; an unknown key is reported, never dropped."""
    return METRIC_UNITS.get(key, UNSPECIFIED_UNIT)


class FigureDoc(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    unit: str
    meaning: str


# Every value this module computes (R1.7).
FIGURES: dict[str, FigureDoc] = {
    "principal": FigureDoc(unit="lines", meaning="Size of the debt: the length of the finding's line range."),
    "interest": FigureDoc(
        unit="lines per year",
        meaning="Yearly cost of leaving the debt unpaid: principal times severity squared.",
    ),
    "effort": FigureDoc(
        unit="effort points",
        meaning="Estimated cost of paying the debt: 1 plus log2 of 1 plus principal.",
    ),
    "interest_per_effort": FigureDoc(
        unit="lines per year per effort point",
        meaning="Interest saved per unit of effort; the plan's ranking key.",
    ),
    "total_principal": FigureDoc(unit="lines", meaning="Sum of principal over the ledger lines."),
    "total_interest": FigureDoc(unit="lines per year", meaning="Sum of interest over the ledger lines."),
    "total_severity": FigureDoc(
        unit="severity points",
        meaning="Sum of severity over the ledger lines; chooses the escalation level.",
    ),
}


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LedgerLine(_Model):
    rank: int
    finding_id: str
    analyzer: str
    file: str
    line_start: int
    line_end: int
    severity: float
    principal: float
    interest: float
    boss: bool
    metrics: dict[str, int | float]


class Coverage(_Model):
    analyzer: str
    returned: int
    matching: int


class Totals(_Model):
    principal: float
    interest: float
    severity: float


class Ledger(_Model):
    snapshot_id: str
    lines: tuple[LedgerLine, ...]
    totals: Totals
    escalation: Level
    coverage: tuple[Coverage, ...]
    truncated: bool


class PlanSource(_Model):
    file: str
    line_start: int
    line_end: int


class PlanEntry(_Model):
    rank: int
    finding_id: str
    source: PlanSource
    effort: float
    interest: float
    interest_per_effort: float
    boss: bool


class PlanResult(_Model):
    snapshot_id: str
    entries: tuple[PlanEntry, ...]


class Priced(NamedTuple):
    """One finding with its computed figures. Internal to this module's callers."""

    finding_id: str
    finding: Finding
    principal: float
    interest: float
    effort: float
    interest_per_effort: float


def price(finding: Finding, finding_id: str) -> Priced:
    """Price one finding (R1.2). Pure."""
    principal = finding.line_end - finding.line_start + 1
    interest = principal * finding.severity**SEVERITY_EXPONENT
    effort = EFFORT_BASE + math.log2(1 + principal)
    return Priced(
        finding_id=finding_id,
        finding=finding,
        principal=round(float(principal), PLACES),
        interest=round(interest, PLACES),
        effort=round(effort, PLACES),
        interest_per_effort=round(interest / effort, PLACES),
    )


def escalation_level(total_severity: float) -> Level:
    """The last level whose cut-off the total reaches. Never falls as the total rises."""
    level = ESCALATION_CUTOFFS[0][0]
    for name, cutoff in ESCALATION_CUTOFFS:
        if total_severity >= cutoff:
            level = name
    return level  # type: ignore[return-value]


def _ledger_order(p: Priced) -> tuple[float, float, str]:
    return (-p.interest, -p.finding.severity, p.finding_id)


def _plan_order(p: Priced) -> tuple[float, float, str]:
    return (-p.interest_per_effort, -p.interest, p.finding_id)


def _price_all(items: Iterable[tuple[Finding, str]]) -> list[Priced]:
    return [price(f, fid) for f, fid in items]


def _boss_ids(ranked: Sequence[Priced]) -> frozenset[str]:
    """Ids of the BOSS_COUNT highest-interest lines, provided interest > 0 (R1.8)."""
    return frozenset(p.finding_id for p in ranked[:BOSS_COUNT] if p.interest > 0)


def build_ledger(
    snapshot_id: str,
    items: Iterable[tuple[Finding, str]],
    coverage: Iterable[Coverage] = (),
) -> Ledger:
    """Rank, total and escalate. Output does not depend on input order (R1.5)."""
    ranked = sorted(_price_all(items), key=_ledger_order)
    bosses = _boss_ids(ranked)
    lines = tuple(
        LedgerLine(
            rank=i,
            finding_id=p.finding_id,
            analyzer=p.finding.analyzer,
            file=p.finding.file,
            line_start=p.finding.line_start,
            line_end=p.finding.line_end,
            severity=p.finding.severity,
            principal=p.principal,
            interest=p.interest,
            boss=p.finding_id in bosses,
            metrics=dict(p.finding.metrics),
        )
        for i, p in enumerate(ranked, start=1)
    )
    # fsum is exactly rounded, so totals do not depend on summation order.
    totals = Totals(
        principal=round(math.fsum(p.principal for p in ranked), PLACES),
        interest=round(math.fsum(p.interest for p in ranked), PLACES),
        severity=round(math.fsum(p.finding.severity for p in ranked), PLACES),
    )
    cov = tuple(sorted(coverage, key=lambda c: c.analyzer))
    return Ledger(
        snapshot_id=snapshot_id,
        lines=lines,
        totals=totals,
        escalation=escalation_level(totals.severity),
        coverage=cov,
        truncated=any(c.returned < c.matching for c in cov),
    )


def build_plan(snapshot_id: str, items: Iterable[tuple[Finding, str]]) -> PlanResult:
    """Same pricing as the ledger, ordered by interest per effort (R5.3).

    Zero-interest debts sort last by the same key and are not omitted.
    """
    priced = _price_all(items)
    bosses = _boss_ids(sorted(priced, key=_ledger_order))
    entries = tuple(
        PlanEntry(
            rank=i,
            finding_id=p.finding_id,
            source=PlanSource(
                file=p.finding.file,
                line_start=p.finding.line_start,
                line_end=p.finding.line_end,
            ),
            effort=p.effort,
            interest=p.interest,
            interest_per_effort=p.interest_per_effort,
            boss=p.finding_id in bosses,
        )
        for i, p in enumerate(sorted(priced, key=_plan_order), start=1)
    )
    return PlanResult(snapshot_id=snapshot_id, entries=entries)
