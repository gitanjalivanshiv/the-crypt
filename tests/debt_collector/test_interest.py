"""Tests for debt-collector/interest.py (R1, R5.2, R5.3)."""

import ast
import importlib
import math
import random
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from skeleton.signals.models import Finding

interest = importlib.import_module("debt-collector.interest")

ROOT = Path(__file__).resolve().parents[2]


def mk(severity=0.5, start=1, end=1, analyzer="churn", file="a.py", metrics=None) -> Finding:
    return Finding(
        analyzer=analyzer,
        file=file,
        line_start=start,
        line_end=end,
        evidence="x",
        severity=severity,
        metrics=metrics or {},
    )


def items(findings):
    return [(f, f"id{i:04d}") for i, f in enumerate(findings)]


findings_st = st.builds(
    lambda sev, start, span, m: mk(severity=sev, start=start, end=start + span, metrics=m),
    st.floats(0.0, 1.0),
    st.integers(1, 1000),
    st.integers(0, 500),
    st.dictionaries(st.sampled_from(["commit_count", "age_days"]), st.integers(0, 5000), max_size=2),
)


# ---- formula, hand computed -------------------------------------------------


def test_one_line_range():
    p = interest.price(mk(0.5, 7, 7), "x")
    assert (p.principal, p.interest, p.effort, p.interest_per_effort) == (1.0, 0.25, 2.0, 0.125)


def test_long_range():
    p = interest.price(mk(0.8, 10, 40), "x")  # principal 31, effort 1 + log2(32) = 6
    assert p.principal == 31.0
    assert p.interest == 19.84
    assert p.effort == 6.0
    assert p.interest_per_effort == 3.306667


def test_severity_zero_and_one():
    zero = interest.price(mk(0.0, 1, 10), "x")
    one = interest.price(mk(1.0, 1, 10), "x")
    assert zero.interest == 0.0 and zero.interest_per_effort == 0.0
    assert one.interest == one.principal == 10.0


def test_rounding_to_six_places():
    p = interest.price(mk(1 / 3, 1, 3), "x")
    assert p.interest == 0.333333
    assert p.interest_per_effort == 0.111111


# ---- properties -------------------------------------------------------------


@given(findings_st)
def test_cp1_finite_non_negative(f):
    p = interest.price(f, "x")
    for v in (p.principal, p.interest, p.effort, p.interest_per_effort):
        assert math.isfinite(v) and v >= 0


@given(st.floats(0.0, 1.0), st.floats(0.0, 1.0), st.integers(1, 500), st.integers(0, 500))
def test_cp2_monotone_in_severity(s1, s2, start, span):
    lo, hi = sorted((s1, s2))
    a = interest.price(mk(lo, start, start + span), "x")
    b = interest.price(mk(hi, start, start + span), "x")
    assert a.interest <= b.interest


@given(st.lists(findings_st, max_size=12), st.randoms(use_true_random=False))
def test_cp3_deterministic_and_shuffle_invariant(fs, rnd):
    pairs = items(fs)
    first = interest.build_ledger("s", pairs)
    assert first == interest.build_ledger("s", pairs)
    shuffled = list(pairs)
    rnd.shuffle(shuffled)
    assert interest.build_ledger("s", shuffled) == first
    assert interest.build_plan("s", shuffled) == interest.build_plan("s", pairs)


# ---- ranking and boss -------------------------------------------------------


def test_ranking_tie_breaks():
    # a, b: equal interest (1 * 1.0 vs 4 * 0.25); b has lower severity. c ties a exactly, id decides.
    a = mk(1.0, 1, 1, file="a.py")
    b = mk(0.5, 1, 4, file="b.py")
    c = mk(1.0, 1, 1, file="c.py")
    ledger = interest.build_ledger("s", [(b, "idB"), (c, "idC"), (a, "idA")])
    assert [line.finding_id for line in ledger.lines] == ["idA", "idC", "idB"]
    assert [line.rank for line in ledger.lines] == [1, 2, 3]


def test_boss_flags_top_with_positive_interest():
    fs = [mk(0.1 * (i + 1), 1, 10) for i in range(6)]
    ledger = interest.build_ledger("s", items(fs))
    assert [line.boss for line in ledger.lines] == [True] * interest.BOSS_COUNT + [False] * (6 - interest.BOSS_COUNT)


def test_no_boss_when_all_interest_zero():
    ledger = interest.build_ledger("s", items([mk(0.0, 1, 5), mk(0.0, 1, 9)]))
    assert not any(line.boss for line in ledger.lines)


def test_boss_only_positive_interest_when_fewer_positive_than_count():
    ledger = interest.build_ledger("s", items([mk(0.5, 1, 5), mk(0.0, 1, 5), mk(0.0, 1, 6)]))
    assert [line.boss for line in ledger.lines] == [True, False, False]


# ---- escalation -------------------------------------------------------------


@given(st.floats(0.0, 1000.0), st.floats(0.0, 1000.0))
def test_cp4_escalation_monotone(a, b):
    lo, hi = sorted((a, b))
    levels = interest.LEVELS
    assert levels.index(interest.escalation_level(lo)) <= levels.index(interest.escalation_level(hi))


def test_cp4_cutoffs_land_on_their_level():
    for name, cutoff in interest.ESCALATION_CUTOFFS:
        assert interest.escalation_level(cutoff) == name
    assert tuple(n for n, _ in interest.ESCALATION_CUTOFFS) == interest.LEVELS


# ---- plan -------------------------------------------------------------------


@given(st.lists(findings_st, max_size=12))
def test_cp6_plan_order_and_same_entries(fs):
    pairs = items(fs)
    ledger = interest.build_ledger("s", pairs)
    plan = interest.build_plan("s", pairs)
    assert sorted(e.finding_id for e in plan.entries) == sorted(line.finding_id for line in ledger.lines)
    keys = [(-e.interest_per_effort, -e.interest, e.finding_id) for e in plan.entries]
    assert keys == sorted(keys)
    assert [e.rank for e in plan.entries] == list(range(1, len(fs) + 1))
    by_id = {line.finding_id: line for line in ledger.lines}
    for e in plan.entries:
        assert e.boss == by_id[e.finding_id].boss
        assert e.interest == by_id[e.finding_id].interest


def test_plan_lists_zero_interest_last():
    plan = interest.build_plan("s", items([mk(0.0, 1, 2), mk(0.5, 1, 20)]))
    assert [e.interest for e in plan.entries] == [5.0, 0.0]


# ---- metric units -----------------------------------------------------------


def _emitted_metric_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "skeleton" / "signals").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.keyword) and node.arg == "metrics" and isinstance(node.value, ast.Dict):
                keys.update(k.value for k in node.value.keys if isinstance(k, ast.Constant))
    return keys


def test_every_emitted_metric_key_has_a_unit():
    emitted = _emitted_metric_keys()
    assert emitted, "AST walk found no metrics= literals"
    assert emitted <= set(interest.METRIC_UNITS)


def test_unknown_metric_key_is_unspecified():
    assert interest.metric_unit("no_such_metric") == "unspecified"
    assert interest.metric_unit("age_days") == "days"


# ---- CP5: payload walk ------------------------------------------------------

POSITIONS = {"rank", "line_start", "line_end", "severity", "returned", "matching"}


def _bad_numbers(node, key=None, in_metrics=False, path="$"):
    bad = []
    if isinstance(node, bool):
        return bad
    if isinstance(node, dict):
        for k, v in node.items():
            bad += _bad_numbers(v, k, in_metrics or k == "metrics", f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            bad += _bad_numbers(v, key, in_metrics, f"{path}[{i}]")
    elif isinstance(node, int | float) and not (in_metrics or key in interest.FIGURES or key in POSITIONS):
        bad.append(path)
    return bad


def test_cp5_every_number_is_metric_figure_or_position():
    fs = [mk(0.9, 1, 12, metrics={"commit_count": 40}), mk(0.2, 5, 9), mk(0.0, 1, 1)]
    cov = [interest.Coverage(analyzer="churn", returned=3, matching=5)]
    ledger = interest.build_ledger("snap", items(fs), cov).model_dump(mode="json")
    plan = interest.build_plan("snap", items(fs)).model_dump(mode="json")
    # Totals fields are named principal/interest/severity, registered as total_* figures.
    assert set(ledger["totals"]) == {"principal", "interest", "severity"}
    assert _bad_numbers(ledger) == []
    assert _bad_numbers(plan) == []
    assert _bad_numbers({"stray": 1.5}) == ["$.stray"]
    assert set(interest.FIGURES) >= {
        "principal", "interest", "effort", "interest_per_effort",
        "total_principal", "total_interest", "total_severity",
    }  # fmt: skip


# ---- empty and misc ---------------------------------------------------------


def test_empty_input():
    ledger = interest.build_ledger("s", [])
    assert ledger.lines == ()
    assert (ledger.totals.principal, ledger.totals.interest, ledger.totals.severity) == (0, 0, 0)
    assert ledger.escalation == "courtesy"
    assert ledger.truncated is False
    assert interest.build_plan("s", []).entries == ()


def test_truncated_flag_from_coverage():
    cov = [interest.Coverage(analyzer="a", returned=100, matching=150)]
    assert interest.build_ledger("s", [], cov).truncated is True


def test_models_are_frozen():
    ledger = interest.build_ledger("s", items([mk()]))
    try:
        ledger.snapshot_id = "other"
    except Exception as e:  # noqa: BLE001
        assert "frozen" in str(e).lower()
    else:
        raise AssertionError("ledger is mutable")


def test_shuffle_helper_sanity():
    fs = [mk(0.1 * i, 1, 3 + i) for i in range(1, 8)]
    pairs = items(fs)
    shuffled = list(pairs)
    random.Random(1).shuffle(shuffled)
    assert interest.build_ledger("s", shuffled) == interest.build_ledger("s", pairs)
