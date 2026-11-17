"""Every ReasonCode has one minimal input that produces it (R4.20, R4.24)."""

from collections.abc import Callable

import pytest

from skeleton.verify.citation import Rejection, verify_citation
from skeleton.verify.claim import verify_claim
from skeleton.verify.codes import MESSAGES, ReasonCode
from skeleton.verify.models import Banishment, VerifyConfig
from tests.verify.fake_view import FakeView

CFG = VerifyConfig()


def _view(snapshot_id: str = "snap-1") -> FakeView:
    return FakeView(
        files={"a.py": b"one\ntwo\n", "bin.py": b"\xff\xfe\n", "b.py": b"x\n"},
        symlinks={"link.py": "a.py"},
        findings={"f1": ("a.py", {"n": 5})},
        snapshot_id=snapshot_id,
    )


def _cite(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {"file": "a.py", "line_start": 1, "line_end": 1}
    base.update(kw)
    return base


def _citation(raw: object) -> ReasonCode:
    result = verify_citation(_view(), raw)
    assert isinstance(result, Rejection)
    return result.code


def _claim(snapshot_id: str = "snap-1", **kw: object) -> ReasonCode:
    raw: dict[str, object] = {"text": "prose", "guess": False, "citations": [_cite()]}
    raw.update(kw)
    result = verify_claim(_view(snapshot_id), raw, 1, CFG)
    assert isinstance(result, Banishment)
    return result.reason


PRODUCERS: dict[ReasonCode, Callable[[], ReasonCode]] = {
    # A citation dict missing keys: verify_claim cannot build a target for it.
    ReasonCode.MALFORMED: lambda: _claim(citations=[{"file": "a.py"}]),
    ReasonCode.PATH_UNSAFE: lambda: _citation(_cite(file="../a.py")),
    ReasonCode.FILE_NOT_FOUND: lambda: _citation(_cite(file="missing.py")),
    ReasonCode.SYMLINK: lambda: _citation(_cite(file="link.py")),
    ReasonCode.RANGE_INVALID: lambda: _citation(_cite(line_start=0)),
    ReasonCode.RANGE_OUT_OF_BOUNDS: lambda: _citation(_cite(line_end=9)),
    ReasonCode.FILE_UNREADABLE: lambda: _citation(_cite(file="bin.py", quote="x")),
    ReasonCode.QUOTE_MISMATCH: lambda: _citation(_cite(quote="nope")),
    ReasonCode.UNCITED_CLAIM: lambda: _claim(citations=[]),
    ReasonCode.FIGURE_NOT_IN_METRICS: lambda: _claim(
        figures=[{"finding_id": "f1", "key": "n", "value": 6}]
    ),
    ReasonCode.FIGURE_NOT_CITED: lambda: _claim(
        citations=[_cite(file="b.py")],
        figures=[{"finding_id": "f1", "key": "n", "value": 5}],
    ),
    # Empty snapshot id: the scan has no id to blank out.
    ReasonCode.UNBACKED_NUMBER: lambda: _claim(snapshot_id="", text="found 42 items"),
}


def test_table_covers_every_reason_code() -> None:
    assert set(PRODUCERS) == set(ReasonCode)
    assert set(MESSAGES) == set(ReasonCode)


@pytest.mark.parametrize("expected", list(ReasonCode), ids=lambda c: c.value)
def test_input_produces_code(expected: ReasonCode) -> None:
    assert PRODUCERS[expected]() is expected
