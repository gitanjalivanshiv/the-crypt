import pytest

from skeleton.verify.claim import verify_claim
from skeleton.verify.codes import ReasonCode
from skeleton.verify.models import Banishment, VerifiedClaim, VerifyConfig
from tests.verify.fake_view import FakeView

CFG = VerifyConfig()
CIT = {"file": "a.py", "line_start": 1, "line_end": 2, "quote": None}
FIG = {"finding_id": "f1", "key": "n", "value": 847}


def view() -> FakeView:
    return FakeView(
        files={"a.py": b"x = 1\ny = 2\n", "b.py": b"z\n"},
        findings={"f1": ("a.py", {"n": 847.0})},
        snapshot_id="snap-1",
    )


def run(raw: object, attempt: int = 2):
    return verify_claim(view(), raw, attempt, CFG)


def claim(**kw):
    base = {"text": "SECRET prose", "guess": False, "citations": [CIT], "figures": []}
    base.update(kw)
    return base


def test_valid_fact_with_figure_float_equals_int():
    r = run(claim(figures=[FIG]))
    assert isinstance(r, VerifiedClaim)
    assert r.kind == "fact" and r.figures[0].value == 847


def test_guess_without_citations_ok():
    r = run(claim(guess=True, citations=[]))
    assert isinstance(r, VerifiedClaim) and r.kind == "guess"


@pytest.mark.parametrize(
    "raw",
    [
        "str",
        None,
        claim(text=""),
        claim(text=5),
        claim(guess="yes"),
        claim(citations="x"),
        claim(figures={}),
        claim(figures=["x"]),
        claim(figures=[{"finding_id": "f1", "key": "n"}]),
        claim(figures=[{"finding_id": 1, "key": "n", "value": 1}]),
        claim(figures=[{"finding_id": "f1", "key": 1, "value": 1}]),
        claim(figures=[{"finding_id": "f1", "key": "n", "value": True}]),
        claim(figures=[{"finding_id": "f1", "key": "n", "value": "847"}]),
        claim(guess=True, figures=[FIG]),
    ],
)
def test_malformed_variants(raw):
    r = run(raw)
    assert isinstance(r, Banishment) and r.reason == ReasonCode.MALFORMED
    assert r.target is None and r.attempt == 2 and r.snapshot_id == "snap-1"


def test_uncited_claim():
    r = run(claim(citations=[]))
    assert r.reason == ReasonCode.UNCITED_CLAIM and r.target is None
    assert r.claim_text == "SECRET prose"


def test_first_failing_citation_with_index():
    bad1 = {"file": "nope.py", "line_start": 1, "line_end": 1}
    bad2 = {"file": "/etc/passwd", "line_start": 1, "line_end": 1}
    r = run(claim(citations=[CIT, bad1, bad2]))
    assert r.reason == ReasonCode.FILE_NOT_FOUND
    assert r.target.type == "citation" and r.target.index == 1
    assert r.target.citation.file == "nope.py"


def test_guess_citations_still_verified():
    r = run(claim(guess=True, citations=[{"file": "nope.py", "line_start": 1, "line_end": 1}]))
    assert r.reason == ReasonCode.FILE_NOT_FOUND


def test_malformed_citation_has_no_target():
    r = run(claim(citations=[CIT, "bad"]))
    assert r.reason == ReasonCode.MALFORMED and r.target is None


@pytest.mark.parametrize(
    "fig",
    [
        {"finding_id": "missing", "key": "n", "value": 847},
        {"finding_id": "f1", "key": "other", "value": 847},
        {"finding_id": "f1", "key": "n", "value": 848},
        {"finding_id": "f1", "key": "n", "value": 847.001},
    ],
)
def test_figure_not_in_metrics(fig):
    r = run(claim(figures=[FIG, fig]))
    assert r.reason == ReasonCode.FIGURE_NOT_IN_METRICS
    assert r.target.type == "figure" and r.target.index == 1


def test_figure_not_cited():
    r = run(claim(citations=[{"file": "b.py", "line_start": 1, "line_end": 1}], figures=[FIG]))
    assert r.reason == ReasonCode.FIGURE_NOT_CITED
    assert r.target.type == "figure" and r.target.index == 0


def test_banishment_messages_contain_no_prose():
    for raw in [
        claim(citations=[]),
        claim(figures=[{**FIG, "value": 1}]),
        claim(citations=[{"file": "b.py", "line_start": 1, "line_end": 1}], figures=[FIG]),
        claim(citations=[{"file": "nope.py", "line_start": 1, "line_end": 1}]),
    ]:
        r = run(raw)
        assert "SECRET" not in r.message
