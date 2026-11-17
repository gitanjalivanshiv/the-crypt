import socket

import pytest

from skeleton.ingest.models import IngestCode, IngestError
from skeleton.ingest.source import validate_url


class Resolver:
    def __init__(self, mapping: dict[str, list[str]] | None = None) -> None:
        self.mapping = mapping or {}
        self.calls: list[str] = []

    def __call__(self, host: str) -> list[str]:
        self.calls.append(host)
        return self.mapping.get(host, ["140.82.112.3"])


def _reject(url: str, resolver: Resolver | None = None, **kw) -> None:
    with pytest.raises(IngestError) as ei:
        validate_url(url, resolver=resolver or Resolver(), **kw)
    assert ei.value.code is IngestCode.invalid_source


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/o/r",
        "ssh://git@github.com/o/r",
        "file:///etc/passwd",
        "/tmp/some/local/path",
        "https://user:pw@github.com/o/r",
        "https://@github.com/o/r",
        "https:///nohost",
        "https://127.0.0.1/o/r",
        "https://10.0.0.1/o/r",
        "https://169.254.169.254/latest",
        "https://[::1]/o/r",
        "https://0.0.0.0/o/r",
    ],
)
def test_rejects_bad_urls(url: str) -> None:
    r = Resolver()
    _reject(url, r)
    assert r.calls == []


def test_mixed_public_and_private_resolution_rejected() -> None:
    r = Resolver({"evil.example": ["140.82.112.3", "10.0.0.5"]})
    _reject("https://evil.example/o/r", r)
    assert r.calls == ["evil.example"]


def test_allowed_hosts_mismatch_rejected() -> None:
    r = Resolver()
    _reject("https://example.com/o/r", r, allowed_hosts=["github.com"])
    assert r.calls == []


def test_resolution_failure_rejected() -> None:
    def boom(host: str) -> list[str]:
        raise socket.gaierror("nope")

    with pytest.raises(IngestError) as ei:
        validate_url("https://github.com/o/r", resolver=boom)
    assert ei.value.code is IngestCode.invalid_source


def test_valid_github_url_passes_and_resolver_is_only_io() -> None:
    r = Resolver()
    parsed = validate_url("https://github.com/o/r", resolver=r, allowed_hosts=["github.com"])
    assert parsed.host == "github.com"
    assert parsed.path == "/o/r"
    assert r.calls == ["github.com"]
