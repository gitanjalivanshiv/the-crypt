import re

import pytest

from skeleton.verify.claim import verify_claim
from skeleton.verify.codes import ReasonCode
from skeleton.verify.models import Banishment, NumberTarget, VerifiedClaim, VerifyConfig
from tests.verify.fake_view import FakeView

TOKEN = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])")
FILE = b"a = 1\nencoding = utf-8\nYEAR = 1999\n"


def run(text: str, quote: str | None = None, figures=(), cfg=None, start=1, end=3):
    view = FakeView(
        files={"a.py": FILE},
        findings={"f1": ("a.py", {"n": 1200, "r": 0.85, "w": 3.0})},
        snapshot_id="abcdef0123456789",
    )
    raw = {
        "text": text,
        "guess": False,
        "citations": [
            {"file": "a.py", "line_start": start, "line_end": end, "quote": quote}
        ],
        "figures": list(figures),
    }
    return verify_claim(view, raw, 1, cfg or VerifyConfig())


def fig(key: str, value):
    return {"finding_id": "f1", "key": key, "value": value}


@pytest.mark.parametrize(
    "s",
    ["utf8", "sha256", "base64", "python3", "oauth2", "s3", "log4j", "md5", "12abc", "a1b2c3"],
)
def test_identifier_digits_not_tokenised(s):
    assert TOKEN.findall(s) == []


@pytest.mark.parametrize("s", ["847", "3.12", "42", "1200", "0", "0.85"])
def test_plain_numbers_tokenised(s):
    assert TOKEN.findall(s) == [s]


def test_identifiers_accepted_in_claims():
    assert isinstance(run("It uses sha256 and python3 here"), VerifiedClaim)


def test_bare_utf_dash_8_banished_backticked_accepted():
    r = run("The file is utf-8 encoded")
    assert isinstance(r, Banishment) and r.reason == ReasonCode.UNBACKED_NUMBER
    assert r.target == NumberTarget(token="8")
    ok = run("The file is `utf-8` encoded", quote="encoding = utf-8", start=2, end=2)
    assert isinstance(ok, VerifiedClaim)


def test_thousands_separator_equals_figure():
    assert isinstance(run("There are 1,200 items", figures=[fig("n", 1200)]), VerifiedClaim)


def test_integral_float_figure_allows_int_and_float_forms():
    assert isinstance(run("About 3 of them", figures=[fig("w", 3.0)]), VerifiedClaim)
    assert isinstance(run("Ratio 0.85", figures=[fig("r", 0.85)]), VerifiedClaim)


def test_line_numbers_and_config_allowed():
    assert isinstance(run("See lines 1 to 3"), VerifiedClaim)
    cfg = VerifyConfig(allowed_numbers=frozenset({"7"}))
    assert isinstance(run("Step 7", cfg=cfg), VerifiedClaim)


def test_snapshot_id_full_and_short_removed():
    assert isinstance(run("Snapshot abcdef0123456789 ok"), VerifiedClaim)
    assert isinstance(run("Snapshot abcdef0 ok"), VerifiedClaim)


def test_arabic_indic_digits_tokenised():
    r = run("There are ٣ of them")
    assert isinstance(r, Banishment) and r.target == NumberTarget(token="٣")


def test_unbacked_plausible_number_rejected():
    r = run("It has been 847 days")
    assert isinstance(r, Banishment) and r.reason == ReasonCode.UNBACKED_NUMBER
    assert r.target == NumberTarget(token="847")


def test_first_unbacked_token_reported():
    r = run("Values 99 then 98")
    assert isinstance(r, Banishment) and r.target == NumberTarget(token="99")


def test_bare_number_present_in_quote_still_banished():
    r = run("The year is 1999", quote="YEAR = 1999", start=3, end=3)
    assert isinstance(r, Banishment) and r.target == NumberTarget(token="1999")


def test_delimited_span_exempt_only_when_in_quote():
    ok = run('It sets "YEAR = 1999"', quote="YEAR = 1999", start=3, end=3)
    assert isinstance(ok, VerifiedClaim)
    bad = run("It sets `YEAR = 2024`", quote="YEAR = 1999", start=3, end=3)
    assert isinstance(bad, Banishment) and bad.target == NumberTarget(token="2024")
    curly = run("It sets “YEAR = 1999”", quote="YEAR = 1999", start=3, end=3)
    assert isinstance(curly, VerifiedClaim)
