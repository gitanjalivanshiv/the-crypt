"""Pure metrics and acceptance bands for the banishment-rate harness (design 5.2, 5.3)."""
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from skeleton.verify.models import AnswerResult


@dataclass(frozen=True)
class Question:
    """Minimal question shape; only id and category matter to the metrics."""

    id: str
    category: str


# Bands (R3.8). Fixed before the first live run; do not tune them to a result.

# Guess share <= 0.35. Too lenient above this: the "guess" flag becomes a
# loophole the model hides behind instead of citing evidence.
GUESS_SHARE_MAX = 0.35
# All-guess turns <= 0.15 of answered turns. Too lenient above this: such a turn
# is the one classify_attempt would route to a decline.
ALL_GUESS_TURNS_MAX = 0.15
# Turns with >= 1 banishment in 0.10..0.50 of turns. Below the lower bound the
# demo has no on-camera banishment; above the upper bound the ghost is unreliable.
BANISHED_TURNS_MIN = 0.10
BANISHED_TURNS_MAX = 0.50
# Declined share <= 0.15. Too strict above this: the demo looks broken.
DECLINED_SHARE_MAX = 0.15
# Verified share >= 0.50. A ghost that mostly guesses or is mostly rejected has
# little to say.
VERIFIED_SHARE_MIN = 0.50


def _share(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


@dataclass(frozen=True)
class Stats:
    turns: int
    answered: int
    declined: int
    judged: int
    verified: int
    guess: int
    banished: int
    banished_by_reason: dict[str, int]
    banished_turns: int
    all_guess_turns: int
    empty_answers: int
    first_attempt_accepted: int

    @property
    def verified_share(self) -> float | None:
        return _share(self.verified, self.judged)

    @property
    def guess_share(self) -> float | None:
        return _share(self.guess, self.judged)

    @property
    def banished_share(self) -> float | None:
        return _share(self.banished, self.judged)

    def reason_share(self, code: str) -> float | None:
        return _share(self.banished_by_reason.get(code, 0), self.judged)

    @property
    def declined_share(self) -> float | None:
        return _share(self.declined, self.turns)

    @property
    def banished_turns_share(self) -> float | None:
        return _share(self.banished_turns, self.turns)

    @property
    def all_guess_share(self) -> float | None:
        return _share(self.all_guess_turns, self.answered)

    @property
    def first_attempt_share(self) -> float | None:
        return _share(self.first_attempt_accepted, self.turns)


@dataclass(frozen=True)
class Report:
    overall: Stats
    by_category: dict[str, Stats] = field(default_factory=dict)


@dataclass(frozen=True)
class Breach:
    scope: str  # "overall" or the category name
    metric: str
    value: float
    band: str


def _stats(results: Iterable[AnswerResult]) -> Stats:
    turns = answered = declined = judged = verified = guess = banished = 0
    banished_turns = all_guess = empty = first_ok = 0
    reasons: Counter[str] = Counter()
    for r in results:
        turns += 1
        if r.status == "declined":
            # Declined turns feed only the declined share, not claim denominators.
            declined += 1
            continue
        answered += 1
        judged += len(r.claims) + len(r.banishments)
        kinds = [c.kind for c in r.claims]
        verified += kinds.count("fact")
        guess += kinds.count("guess")
        banished += len(r.banishments)
        reasons.update(str(b.reason.value) for b in r.banishments)
        if r.banishments:
            banished_turns += 1
        if r.attempts and r.attempts[0].outcome == "accepted":
            first_ok += 1
        if not r.claims:
            empty += 1
        elif all(k == "guess" for k in kinds):
            all_guess += 1
    return Stats(
        turns, answered, declined, judged, verified, guess, banished,
        dict(reasons), banished_turns, all_guess, empty, first_ok,
    )


def compute(results: list[tuple[Question, AnswerResult]]) -> Report:
    by_cat: dict[str, list[AnswerResult]] = {}
    for q, r in results:
        by_cat.setdefault(q.category, []).append(r)
    return Report(
        overall=_stats(r for _, r in results),
        by_category={c: _stats(rs) for c, rs in sorted(by_cat.items())},
    )


def _check(scope: str, s: Stats) -> list[Breach]:
    out: list[Breach] = []

    def upper(name: str, v: float | None, mx: float) -> None:
        if v is not None and v > mx:
            out.append(Breach(scope, name, v, f"<= {mx}"))

    upper("guess_share", s.guess_share, GUESS_SHARE_MAX)
    upper("all_guess_turns", s.all_guess_share, ALL_GUESS_TURNS_MAX)
    upper("declined_share", s.declined_share, DECLINED_SHARE_MAX)
    bt = s.banished_turns_share
    if bt is not None and not (BANISHED_TURNS_MIN <= bt <= BANISHED_TURNS_MAX):
        out.append(
            Breach(scope, "banished_turns", bt, f"{BANISHED_TURNS_MIN}..{BANISHED_TURNS_MAX}")
        )
    vs = s.verified_share
    if vs is not None and vs < VERIFIED_SHARE_MIN:
        out.append(Breach(scope, "verified_share", vs, f">= {VERIFIED_SHARE_MIN}"))
    return out


def breaches(report: Report) -> list[Breach]:
    """Band breaches overall and per category. Undefined (None) metrics are skipped."""
    out = _check("overall", report.overall)
    for cat, s in report.by_category.items():
        out += _check(cat, s)
    return out


def _fmt(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{num}/{den} ({num / den:.1%})"


def _render_stats(s: Stats) -> list[str]:
    lines = [
        f"  turns: {s.turns} (answered {s.answered}, declined {s.declined}, "
        f"empty answers {s.empty_answers})",
        f"  verified share: {_fmt(s.verified, s.judged)}",
        f"  guess share: {_fmt(s.guess, s.judged)}",
        f"  banished share: {_fmt(s.banished, s.judged)}",
    ]
    for code in sorted(s.banished_by_reason):
        lines.append(f"    {code}: {_fmt(s.banished_by_reason[code], s.judged)}")
    lines += [
        f"  turns with banishment: {_fmt(s.banished_turns, s.turns)}",
        f"  all-guess turns: {_fmt(s.all_guess_turns, s.answered)}",
        f"  declined share: {_fmt(s.declined, s.turns)}",
        f"  first-attempt accepted: {_fmt(s.first_attempt_accepted, s.turns)}",
    ]
    return lines


def render(report: Report) -> str:
    lines = ["overall"] + _render_stats(report.overall)
    for cat, s in report.by_category.items():
        lines += [f"category {cat}"] + _render_stats(s)
    return "\n".join(lines)
