"""Tests for medium.eval.metrics (R3.6 to R3.9)."""
from hypothesis import given
from hypothesis import strategies as st

from medium.eval.metrics import Question, breaches, compute, render
from skeleton.verify.codes import ReasonCode
from skeleton.verify.models import (
    AnswerResult,
    AttemptRecord,
    Banishment,
    VerifiedClaim,
)


def claim(kind: str) -> VerifiedClaim:
    return VerifiedClaim(kind=kind, text="t")  # type: ignore[arg-type]


def ban(reason: ReasonCode = ReasonCode.UNCITED_CLAIM) -> Banishment:
    return Banishment(claim_text="c", reason=reason, message="m", attempt=1, snapshot_id="s")


def att(*outcomes: str) -> tuple[AttemptRecord, ...]:
    return tuple(AttemptRecord(attempt=i + 1, outcome=o) for i, o in enumerate(outcomes))  # type: ignore[arg-type]


def answered(kinds=(), bans=(), attempts=("accepted",)) -> AnswerResult:
    return AnswerResult(
        snapshot_id="s", status="answered",
        claims=tuple(claim(k) for k in kinds), banishments=tuple(bans), attempts=att(*attempts),
    )


def declined() -> AnswerResult:
    return AnswerResult(snapshot_id="s", status="declined", decline_line="no", attempts=att("banished"))


Q = Question("q", "churn")


def run(*rs: AnswerResult, cat: str = "churn"):
    return compute([(Question("q", cat), r) for r in rs])


def test_exact_shares_mixed():
    rep = run(
        answered(["fact", "fact"]),                                    # all fact
        answered(["guess"]),                                           # all guess
        declined(),
        answered(["fact", "guess"], [ban(ReasonCode.QUOTE_MISMATCH)], ("banished", "accepted")),
    )
    s = rep.overall
    assert (s.turns, s.answered, s.declined, s.judged) == (4, 3, 1, 6)
    assert (s.verified, s.guess, s.banished) == (3, 2, 1)
    assert s.verified_share == 0.5 and s.guess_share == 2 / 6 and s.banished_share == 1 / 6
    assert s.reason_share("quote_mismatch") == 1 / 6
    assert s.declined_share == 0.25
    assert s.all_guess_turns == 1 and s.all_guess_share == 1 / 3
    assert s.banished_turns == 1 and s.banished_turns_share == 0.25
    assert s.first_attempt_accepted == 2 and s.first_attempt_share == 0.5
    assert rep.by_category["churn"] == s


def test_declined_not_in_claim_denominators():
    s = run(answered(["fact"]), declined()).overall
    assert s.judged == 1 and s.verified_share == 1.0 and s.declined_share == 0.5


def test_empty_answers_separate():
    s = run(answered([]), answered(["fact"])).overall
    assert s.empty_answers == 1 and s.all_guess_turns == 0


def test_per_category():
    rep = compute([(Question("a", "x"), answered(["fact"])), (Question("b", "y"), answered(["guess"]))])
    assert rep.by_category["x"].verified_share == 1.0
    assert rep.by_category["y"].guess_share == 1.0


def test_na_with_zero_judged():
    s = run(declined()).overall
    assert s.judged == 0 and s.verified_share is None and s.guess_share is None
    assert s.banished_share is None and s.reason_share("malformed") is None
    out = render(run(declined()))
    assert "verified share: n/a" in out and "declined share: 1/1 (100.0%)" in out
    names = {b.metric for b in breaches(run(declined()))}
    assert not names & {"verified_share", "guess_share", "all_guess_turns"}


def metrics_of(rep):
    return {b.metric for b in breaches(rep) if b.scope == "overall"}


def test_each_band_breach():
    assert "guess_share" in metrics_of(run(answered(["fact", "guess"])))
    assert "all_guess_turns" in metrics_of(run(answered(["guess"]), answered(["fact"] * 3 + ["guess"] * 0)))
    assert "banished_turns" in metrics_of(run(answered(["fact"])))  # 0 < 0.10
    assert "banished_turns" in metrics_of(run(answered(["fact"], [ban()])))  # 1.0 > 0.50
    assert "declined_share" in metrics_of(run(declined(), answered(["fact"])))
    assert "verified_share" in metrics_of(run(answered(["fact"], [ban(), ban()])))


def test_no_breach_in_band():
    rs = [answered(["fact"] * 4 + ["guess"])] * 5 + [answered(["fact"] * 5, [ban()])] * 5
    assert breaches(run(*rs)) == []


def test_render_counts_beside_shares():
    out = render(run(answered(["fact", "guess"])))
    assert "verified share: 1/2 (50.0%)" in out and "category churn" in out


results_st = st.lists(
    st.one_of(
        st.just(declined()),
        st.builds(
            answered,
            st.lists(st.sampled_from(["fact", "guess"]), max_size=5),
            st.lists(st.sampled_from(list(ReasonCode)).map(ban), max_size=5),
        ),
    ),
    max_size=15,
)


@given(results_st)
def test_mp6_partition(rs):
    """MP6. **Validates: Requirements 3.6, 3.7**"""
    s = run(*rs).overall
    assert s.verified + s.guess + s.banished == s.judged
    if s.judged:
        assert abs(sum(s.reason_share(c) for c in s.banished_by_reason) - s.banished_share) < 1e-9


@given(st.integers(0, 6))
def test_mp7_na_not_zero(n):
    """MP7. **Validates: Requirements 3.9**"""
    s = run(*[declined()] * n).overall
    assert s.verified_share is None and s.guess_share is None and s.banished_share is None
