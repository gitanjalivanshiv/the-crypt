"""Source URL validation. Runs before any network or filesystem access."""

import ipaddress
import socket
from collections.abc import Callable, Collection
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from skeleton.ingest.models import IngestCode, IngestError

Resolver = Callable[[str], list[str]]


class ParsedSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    host: str
    path: str


def default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


def _invalid(detail: str) -> IngestError:
    return IngestError(IngestCode.invalid_source, detail)


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def validate_url(
    url: str,
    *,
    resolver: Resolver = default_resolver,
    allowed_hosts: Collection[str] | None = None,
) -> ParsedSource:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        _ = parts.port
    except ValueError as exc:
        raise _invalid(f"malformed URL: {exc}") from exc
    if parts.scheme != "https":
        raise _invalid("only https URLs are accepted")
    if not host:
        raise _invalid("URL has no hostname")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise _invalid("URL must not contain credentials")
    if allowed_hosts is not None and host not in {h.lower() for h in allowed_hosts}:
        raise _invalid(f"host not allowed: {host}")
    try:
        ipaddress.ip_address(host)
        addrs = [host]
    except ValueError:
        try:
            addrs = list(resolver(host))
        except OSError as exc:
            raise _invalid(f"cannot resolve host: {host}") from exc
    if not addrs:
        raise _invalid(f"host did not resolve: {host}")
    for addr in addrs:
        try:
            public = _is_public(addr)
        except ValueError:
            raise _invalid(f"invalid resolved address for {host}") from None
        if not public:
            raise _invalid(f"host resolves to a non-public address: {host}")
    return ParsedSource(url=url, host=host, path=parts.path)
