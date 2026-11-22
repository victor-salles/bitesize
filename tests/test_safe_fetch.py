import socket
from unittest.mock import MagicMock

import pytest

import safe_fetch
from safe_fetch import FetchError, Reason

PUBLIC_IP = "93.184.215.14"


@pytest.fixture
def addresses(monkeypatch):
    """Map host -> IPs for getaddrinfo; unknown hosts resolve to PUBLIC_IP, literals to themselves."""
    table: dict[str, list[str]] = {}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        ips = table.get(host)
        if ips is None:
            ips = [host] if host[0].isdigit() or ":" in host else [PUBLIC_IP]
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    return table


class FakeResponse:
    def __init__(self, status=200, body=b"ok", location=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.body = body

    def iter_content(self, chunk_size=1):
        yield self.body

    def close(self):
        pass


def test_resolve_pins_the_checked_address(addresses):
    target = safe_fetch.resolve("https://example.com/feed?x=1")

    assert target == safe_fetch.Target(
        url="https://example.com/feed?x=1", scheme="https", hostname="example.com", port=443, address=PUBLIC_IP
    )
    assert target.pinned_url == f"https://{PUBLIC_IP}/feed?x=1"
    assert target.host_header == "example.com"


def test_pinned_url_brackets_ipv6(addresses):
    addresses["v6.example"] = ["2606:2800:21f:cb07:6820:80da:af6b:8b2c"]

    target = safe_fetch.resolve("http://v6.example/a")

    assert target.pinned_url == "http://[2606:2800:21f:cb07:6820:80da:af6b:8b2c]/a"


@pytest.mark.parametrize(
    "url,reason",
    [
        ("file:///etc/passwd", Reason.SCHEME),
        ("https://example.com:8443/", Reason.PORT),
        ("http://10.0.0.5/admin", Reason.PRIVATE),
        ("http://169.254.169.254/latest/", Reason.PRIVATE),
    ],
)
def test_resolve_refuses_by_policy(addresses, url, reason):
    with pytest.raises(FetchError) as excinfo:
        safe_fetch.resolve(url)

    assert (excinfo.value.reason, excinfo.value.blocked) == (reason, True)


def test_allow_private_lifts_the_address_and_port_rules(addresses):
    addresses["nas.local"] = ["192.168.1.10"]

    target = safe_fetch.resolve("http://nas.local:8080/feed", allow_private=True)

    assert (target.address, target.pinned_url, target.host_header) == (
        "192.168.1.10",
        "http://192.168.1.10:8080/feed",
        "nas.local:8080",
    )


def test_allow_private_keeps_the_scheme_rule(addresses):
    with pytest.raises(FetchError) as excinfo:
        safe_fetch.resolve("file:///etc/passwd", allow_private=True)

    assert excinfo.value.reason is Reason.SCHEME


def test_open_connects_to_the_address_and_keeps_the_hostname(addresses):
    session = MagicMock()
    target = safe_fetch.resolve("https://example.com/feed")

    safe_fetch._open(session, target, timeout=7, headers={"User-Agent": "ua"})

    session.get.assert_called_once()
    args, kwargs = session.get.call_args
    assert args == (f"https://{PUBLIC_IP}/feed",)
    assert kwargs["headers"] == {"User-Agent": "ua", "Host": "example.com"}
    assert (kwargs["timeout"], kwargs["allow_redirects"], kwargs["stream"]) == (7, False, True)
    assert session.trust_env is False
    (prefix, adapter), _ = session.mount.call_args
    assert prefix == "https://"
    assert adapter.poolmanager.connection_pool_kw["server_hostname"] == "example.com"
    assert adapter.poolmanager.connection_pool_kw["assert_hostname"] == "example.com"


def test_fetch_rechecks_every_redirect(addresses, monkeypatch):
    addresses["metadata.internal"] = ["169.254.169.254"]
    opened = []

    def fake_open(_session, target, **kwargs):
        opened.append(target.url)
        return FakeResponse(302, location="http://metadata.internal/latest/")

    monkeypatch.setattr(safe_fetch, "_open", fake_open)

    with pytest.raises(FetchError) as excinfo:
        safe_fetch.fetch("https://example.com/a", timeout=5, user_agent="ua")

    assert (excinfo.value.reason, excinfo.value.url) == (Reason.PRIVATE, "http://metadata.internal/latest/")
    assert opened == ["https://example.com/a"]


def test_fetch_returns_the_body_after_a_public_redirect(addresses, monkeypatch):
    responses = {
        "https://example.com/a": FakeResponse(301, location="/b"),
        "https://example.com/b": FakeResponse(200, b"body"),
    }
    monkeypatch.setattr(safe_fetch, "_open", lambda _session, target, **kwargs: responses[target.url])

    assert safe_fetch.fetch("https://example.com/a", timeout=5, user_agent="ua") == b"body"


def test_fetch_reports_http_errors_with_their_status(addresses, monkeypatch):
    monkeypatch.setattr(safe_fetch, "_open", lambda _session, target, **kwargs: FakeResponse(404))

    with pytest.raises(FetchError) as excinfo:
        safe_fetch.fetch("https://example.com/a", timeout=5, user_agent="ua")

    assert (excinfo.value.reason, excinfo.value.status_code, excinfo.value.blocked) == (Reason.HTTP_ERROR, 404, False)
