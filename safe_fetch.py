"""Fetch http(s) URLs from public addresses only.

Feed and article URLs come from users and from the feeds themselves, so every
fetch the server makes goes through here: http or https on port 80 or 443, to
a host whose addresses are all public (no loopback, private, link-local,
reserved or multicast). Redirects are followed one hop at a time and each hop
is checked again. The connection goes to the address that was checked, so the
host cannot resolve somewhere else between the check and the request (DNS
rebinding).

`allow_private=True` lifts the port and address rules for a single-user setup
that reads feeds on its own network. The scheme rule always applies.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin, urlsplit, urlunsplit

import certifi
import requests
from requests.adapters import HTTPAdapter

DEFAULT_PORTS = {"http": 80, "https": 443}
ALLOWED_PORTS = {80, 443}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class Reason(Enum):
    SCHEME = "scheme"
    PORT = "port"
    UNRESOLVED = "unresolved"
    PRIVATE = "private"
    TOO_MANY_REDIRECTS = "too many redirects"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    HTTP_ERROR = "http error"
    TOO_LARGE = "too large"
    INTERRUPTED = "interrupted"


# Refused by policy, as opposed to a site that is down or answered badly.
BLOCKED = {Reason.SCHEME, Reason.PORT, Reason.PRIVATE}


class FetchError(Exception):
    def __init__(self, reason: Reason, url: str, status_code: int | None = None):
        self.reason = reason
        self.url = url
        self.status_code = status_code
        detail = f" {status_code}" if status_code is not None else ""
        super().__init__(f"{reason.value}{detail}: {url}")

    @property
    def blocked(self) -> bool:
        return self.reason in BLOCKED


@dataclass(frozen=True)
class Target:
    """A checked URL and the address its connection must go to."""

    url: str
    scheme: str
    hostname: str
    port: int
    address: str

    @property
    def host_header(self) -> str:
        host = f"[{self.hostname}]" if ":" in self.hostname else self.hostname
        return host if self.port == DEFAULT_PORTS[self.scheme] else f"{host}:{self.port}"

    @property
    def pinned_url(self) -> str:
        """The URL with its host replaced by the checked address."""
        parts = urlsplit(self.url)
        host = f"[{self.address}]" if ":" in self.address else self.address
        netloc = host if self.port == DEFAULT_PORTS[self.scheme] else f"{host}:{self.port}"
        return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop an IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved)


def resolve(url: str, *, allow_private: bool = False) -> Target:
    """Check `url` against the rules and return where to connect. Raise FetchError if refused."""
    parts = urlsplit(url)
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname:
        raise FetchError(Reason.SCHEME, url)
    try:
        port = parts.port or DEFAULT_PORTS[parts.scheme]
    except ValueError:
        raise FetchError(Reason.PORT, url) from None
    if port not in ALLOWED_PORTS and not allow_private:
        raise FetchError(Reason.PORT, url)
    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise FetchError(Reason.UNRESOLVED, url) from exc
    addresses = [info[4][0] for info in infos]
    if not addresses:
        raise FetchError(Reason.UNRESOLVED, url)
    if not allow_private and not all(is_public(address) for address in addresses):
        raise FetchError(Reason.PRIVATE, url)
    return Target(url=url, scheme=parts.scheme, hostname=parts.hostname, port=port, address=addresses[0])


def fetch(
    url: str,
    *,
    timeout: float,
    user_agent: str,
    max_bytes: int | None = None,
    max_redirects: int = 5,
    allow_private: bool = False,
) -> bytes:
    """Return the body at `url`, following up to `max_redirects` checked redirects."""
    for _hop in range(max_redirects + 1):
        target = resolve(url, allow_private=allow_private)
        with requests.Session() as session:
            response = _request(session, target, timeout=timeout, user_agent=user_agent)
            try:
                location = response.headers.get("Location")
                if response.status_code not in REDIRECT_STATUSES or not location:
                    return _read_body(response, url, max_bytes)
            finally:
                response.close()
        url = urljoin(url, location)
    raise FetchError(Reason.TOO_MANY_REDIRECTS, url)


def _request(session: requests.Session, target: Target, *, timeout: float, user_agent: str) -> requests.Response:
    try:
        return _open(session, target, timeout=timeout, headers={"User-Agent": user_agent})
    except requests.Timeout as exc:
        raise FetchError(Reason.TIMEOUT, target.url) from exc
    except requests.RequestException as exc:
        raise FetchError(Reason.UNREACHABLE, target.url) from exc


def _open(session: requests.Session, target: Target, *, timeout: float, headers: dict) -> requests.Response:
    """Send one GET for `target` to its checked address, keeping the hostname for Host, SNI and the certificate."""
    session.trust_env = False  # a proxy would do its own lookup
    if target.scheme == "https":
        session.mount("https://", _PinnedHostAdapter(target.hostname))
    return session.get(
        target.pinned_url,
        timeout=timeout,
        headers={**headers, "Host": target.host_header},
        verify=certifi.where(),
        allow_redirects=False,
        stream=True,
    )


class _PinnedHostAdapter(HTTPAdapter):
    """Connect to an address but verify TLS against the original hostname."""

    def __init__(self, hostname: str):
        self._hostname = hostname
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["server_hostname"] = self._hostname
        kwargs["assert_hostname"] = self._hostname
        super().init_poolmanager(*args, **kwargs)


def _read_body(response: requests.Response, url: str, max_bytes: int | None) -> bytes:
    if response.status_code >= 400:
        raise FetchError(Reason.HTTP_ERROR, url, status_code=response.status_code)
    body = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if max_bytes is not None and len(body) > max_bytes:
                raise FetchError(Reason.TOO_LARGE, url)
    except requests.RequestException as exc:
        raise FetchError(Reason.INTERRUPTED, url) from exc
    return bytes(body)
