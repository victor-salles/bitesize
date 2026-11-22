import ipaddress
import json
import socket
from io import StringIO

import pytest
import requests
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.urls import reverse

import safe_fetch
from core.models import Source
from sources import catalogue, feeds
from sources.starter import add_starter_sources

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Example News</title>
<item><title>One</title><link>https://example.com/1</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Blog</title>
<entry><title>Post</title><link href="https://blog.example/post"/></entry>
</feed>"""

HTML = b"<!doctype html><html><head><title>Not a feed</title></head><body><p>Hello</p></body></html>"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, location: str | None = None):
        self.body = body
        self.status_code = status
        self.headers = {"Location": location} if location else {}

    @property
    def is_redirect(self):
        return "Location" in self.headers and self.status_code in (301, 302, 303, 307, 308)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i : i + chunk_size]

    def close(self):
        pass


PUBLIC_IP = "93.184.215.14"


@pytest.fixture
def network(monkeypatch):
    """Serve fake bytes for any URL and resolve every host to a public IP; record
    the calls. Never touches the network or DNS.

    `state["addresses"]` maps a host to the IPs it resolves to; `state["redirects"]`
    maps a URL to the Location it redirects to.
    """
    calls = []
    state = {"body": RSS, "status": 200, "error": None, "addresses": {}, "redirects": {}}

    def fake_open(_session, target, **kwargs):
        url = target.url
        calls.append((url, kwargs))
        if state["error"]:
            raise state["error"]
        if url in state["redirects"]:
            return FakeResponse(b"", 302, location=state["redirects"][url])
        return FakeResponse(state["body"], state["status"])

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host not in state["addresses"] and host.startswith("unknown."):
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        try:
            addresses = [str(ipaddress.ip_address(host))]  # a literal resolves to itself
        except ValueError:
            addresses = state["addresses"].get(host, [PUBLIC_IP])
        return [
            (socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
            for ip in addresses
        ]

    monkeypatch.setattr(safe_fetch, "_open", fake_open)
    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    state["calls"] = calls
    return state


@pytest.fixture
def ana(db):
    return User.objects.create_user(username="ana", password="x")


@pytest.fixture
def bia(db):
    return User.objects.create_user(username="bia", password="x")


@pytest.fixture
def client_ana(client, ana):
    client.force_login(ana)
    return client


@pytest.fixture
def small_catalogue(tmp_path, settings):
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            {
                "categories": {
                    "Tech": {"The Verge": "https://www.theverge.com/rss/index.xml"},
                    "World": {
                        "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
                        "NPR News": "https://feeds.npr.org/1001/rss.xml",
                    },
                },
                "integrations": {"gmail": False},
            }
        )
    )
    settings.SOURCES_CATALOGUE_PATH = path
    return path


# ── Feed validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("body,title", [(RSS, "Example News"), (ATOM, "Atom Blog")])
def test_validate_feed_accepts_rss_and_atom(network, body, title):
    network["body"] = body

    assert feeds.validate_feed("https://example.com/feed") == title


def test_validate_feed_uses_a_timeout(network):
    feeds.validate_feed("https://example.com/feed")

    (_url, kwargs) = network["calls"][0]
    assert kwargs["timeout"] == feeds.TIMEOUT_SECONDS


def test_validate_feed_rejects_html(network):
    network["body"] = HTML

    with pytest.raises(feeds.FeedError, match="RSS or Atom"):
        feeds.validate_feed("https://example.com/")


def test_validate_feed_reports_http_errors(network):
    network["status"] = 404

    with pytest.raises(feeds.FeedError, match="404"):
        feeds.validate_feed("https://example.com/feed")


def test_validate_feed_reports_timeouts(network):
    network["error"] = requests.Timeout("read timed out")

    with pytest.raises(feeds.FeedError, match="did not answer"):
        feeds.validate_feed("https://example.com/feed")


def test_validate_feed_rejects_oversized_responses(network, monkeypatch):
    monkeypatch.setattr(feeds, "MAX_BYTES", 10)

    with pytest.raises(feeds.FeedError, match="too large"):
        feeds.validate_feed("https://example.com/feed")


# ── Private addresses (SSRF) ─────────────────────────────────────────────────

PRIVATE_NETWORK = "That address points to a private network, which a feed cannot use."


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # private
        "172.17.0.2",  # private (Docker / Dokku network)
        "192.168.1.10",  # private
        "169.254.169.254",  # link-local (cloud metadata)
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",  # unspecified
        "224.0.0.1",  # multicast
        "240.0.0.1",  # reserved
        "::1",  # IPv6 loopback
        "fe80::1",  # IPv6 link-local
        "fc00::1",  # IPv6 unique local
        "ff02::1",  # IPv6 multicast
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:10.0.0.1",  # IPv4-mapped private
    ],
)
def test_validate_feed_refuses_hosts_that_resolve_to_non_public_ips(network, ip):
    network["addresses"]["internal.example"] = [ip]

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://internal.example/feed")

    assert str(excinfo.value) == PRIVATE_NETWORK
    assert network["calls"] == []


def test_validate_feed_refuses_a_host_with_any_private_ip(network):
    network["addresses"]["mixed.example"] = [PUBLIC_IP, "10.0.0.1"]

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://mixed.example/feed")

    assert str(excinfo.value) == PRIVATE_NETWORK
    assert network["calls"] == []


@pytest.mark.parametrize("url", ["http://127.0.0.1/feed", "http://[::1]/feed", "http://localhost/feed"])
def test_validate_feed_refuses_literal_and_local_hosts(network, url):
    network["addresses"]["localhost"] = ["127.0.0.1"]

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed(url)

    assert str(excinfo.value) == PRIVATE_NETWORK
    assert network["calls"] == []


def test_validate_feed_allows_public_ipv6(network):
    network["addresses"]["v6.example"] = ["2606:2800:21f:cb07:6820:80da:af6b:8b2c"]

    assert feeds.validate_feed("https://v6.example/feed") == "Example News"


@pytest.mark.parametrize("url", ["https://example.com:443/feed", "http://example.com:80/feed"])
def test_validate_feed_allows_the_standard_ports(network, url):
    assert feeds.validate_feed(url) == "Example News"


@pytest.mark.parametrize("url", ["https://example.com:8443/feed", "http://example.com:22/feed"])
def test_validate_feed_refuses_other_ports(network, url):
    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed(url)

    assert str(excinfo.value) == "A feed must use the standard web ports (80 or 443)."
    assert network["calls"] == []


@pytest.mark.parametrize("url", ["ftp://example.com/feed", "file:///etc/passwd", "gopher://example.com/"])
def test_validate_feed_refuses_other_schemes(network, url):
    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed(url)

    assert str(excinfo.value) == "A feed address must start with http:// or https://."
    assert network["calls"] == []


def test_validate_feed_reports_unknown_hosts(network):
    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://unknown.example/feed")

    assert str(excinfo.value) == "Could not find that address."
    assert network["calls"] == []


def test_validate_feed_follows_redirects_to_public_hosts(network):
    network["redirects"]["https://example.com/feed"] = "/rss"
    network["redirects"]["https://example.com/rss"] = "https://cdn.example/rss.xml"

    assert feeds.validate_feed("https://example.com/feed") == "Example News"
    assert [url for url, _kwargs in network["calls"]] == [
        "https://example.com/feed",
        "https://example.com/rss",
        "https://cdn.example/rss.xml",
    ]


def test_validate_feed_refuses_a_redirect_to_a_private_ip(network):
    network["addresses"]["metadata.internal"] = ["169.254.169.254"]
    network["redirects"]["https://example.com/feed"] = "http://metadata.internal/latest/"

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://example.com/feed")

    assert str(excinfo.value) == PRIVATE_NETWORK
    assert [url for url, _kwargs in network["calls"]] == ["https://example.com/feed"]


def test_validate_feed_refuses_a_redirect_to_another_scheme(network):
    network["redirects"]["https://example.com/feed"] = "file:///etc/passwd"

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://example.com/feed")

    assert str(excinfo.value) == "A feed address must start with http:// or https://."


def test_validate_feed_stops_after_too_many_redirects(network):
    network["redirects"]["https://example.com/a"] = "https://example.com/b"
    network["redirects"]["https://example.com/b"] = "https://example.com/a"

    with pytest.raises(feeds.FeedError) as excinfo:
        feeds.validate_feed("https://example.com/a")

    assert str(excinfo.value) == "That address redirected too many times."
    assert len(network["calls"]) == feeds.MAX_REDIRECTS + 1


def test_add_refuses_a_private_address(client_ana, ana, network):
    network["addresses"]["router.example"] = ["192.168.0.1"]

    response = client_ana.post(
        reverse("sources:add"), {"url": "http://router.example/feed", "name": "X", "category": "Tech"}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["url"] == [PRIVATE_NETWORK]
    assert not Source.objects.filter(user=ana).exists()


# ── Catalogue ────────────────────────────────────────────────────────────────


def test_catalogue_reads_the_repo_sources_json():
    with open(catalogue.default_path()) as handle:
        expected = json.load(handle)["categories"]

    assert catalogue.load() == expected


def test_catalogue_lookup(small_catalogue):
    assert catalogue.lookup("World", "NPR News") == "https://feeds.npr.org/1001/rss.xml"
    assert catalogue.lookup("World", "Nope") is None
    assert catalogue.lookup("Nope", "NPR News") is None


# ── Login ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["sources:list"])
def test_list_requires_login(client, name):
    response = client.get(reverse(name))

    assert response.status_code == 302
    assert "next=" in response["Location"]


@pytest.mark.django_db
def test_post_views_require_login(client, ana):
    source = Source.objects.create(user=ana, name="A", url="https://a.example/rss", category="X")

    for url in [
        reverse("sources:add"),
        reverse("sources:pick"),
        reverse("sources:toggle", args=[source.pk]),
        reverse("sources:delete", args=[source.pk]),
    ]:
        assert client.post(url).status_code == 302
    source.refresh_from_db()
    assert source.active


# ── List ─────────────────────────────────────────────────────────────────────


def test_list_shows_only_my_sources_grouped_by_category(client_ana, ana, bia, small_catalogue):
    Source.objects.create(user=ana, name="Mine", url="https://mine.example/rss", category="Tech")
    Source.objects.create(user=bia, name="Hers", url="https://hers.example/rss", category="Tech")

    response = client_ana.get(reverse("sources:list"))

    assert response.status_code == 200
    body = response.content.decode()
    assert "Mine" in body
    assert "Hers" not in body
    assert "BBC World" in body  # catalogue offered


def test_list_marks_catalogue_entries_already_added(client_ana, ana, small_catalogue):
    Source.objects.create(user=ana, name="BBC", url="http://feeds.bbci.co.uk/news/world/rss.xml", category="World")

    response = client_ana.get(reverse("sources:list"))

    world = dict(response.context["catalogue"])["World"]
    added = {entry["name"]: entry["added"] for entry in world}
    assert added == {"BBC World": True, "NPR News": False}


def test_list_has_no_javascript(client_ana, small_catalogue):
    response = client_ana.get(reverse("sources:list"))

    assert b"<script" not in response.content


# ── Add by URL ───────────────────────────────────────────────────────────────


def test_add_validates_and_saves(client_ana, ana, network):
    response = client_ana.post(
        reverse("sources:add"), {"url": "https://example.com/feed", "name": "", "category": "Tech"}
    )

    assert response.status_code == 302
    source = Source.objects.get(user=ana)
    assert source.name == "Example News"  # taken from the feed when left blank
    assert source.url == "https://example.com/feed"
    assert source.category == "Tech"
    assert source.active


def test_add_keeps_the_given_name(client_ana, ana, network):
    client_ana.post(reverse("sources:add"), {"url": "https://example.com/feed", "name": "Mine", "category": "Tech"})

    assert Source.objects.get(user=ana).name == "Mine"


def test_add_rejects_a_url_that_is_not_a_feed(client_ana, ana, network):
    network["body"] = HTML

    response = client_ana.post(
        reverse("sources:add"), {"url": "https://example.com/", "name": "X", "category": "Tech"}
    )

    assert response.status_code == 200
    assert "url" in response.context["form"].errors
    assert not Source.objects.filter(user=ana).exists()


def test_add_rejects_a_url_the_server_cannot_reach(client_ana, ana, network):
    network["error"] = requests.ConnectionError("nope")

    response = client_ana.post(
        reverse("sources:add"), {"url": "https://down.example/feed", "name": "X", "category": "Tech"}
    )

    assert response.status_code == 200
    assert "url" in response.context["form"].errors
    assert not Source.objects.filter(user=ana).exists()


@pytest.mark.parametrize("url", ["ftp://example.com/feed", "not a url", ""])
def test_add_rejects_non_http_urls_without_fetching(client_ana, ana, network, url):
    response = client_ana.post(reverse("sources:add"), {"url": url, "name": "X", "category": "Tech"})

    assert response.status_code == 200
    assert "url" in response.context["form"].errors
    assert network["calls"] == []


def test_add_requires_a_category(client_ana, ana, network):
    response = client_ana.post(reverse("sources:add"), {"url": "https://example.com/feed", "name": "X", "category": " "})

    assert "category" in response.context["form"].errors
    assert not Source.objects.filter(user=ana).exists()


def test_add_rejects_a_duplicate_url_without_fetching(client_ana, ana, network):
    Source.objects.create(user=ana, name="Old", url="https://example.com/feed", category="Tech")

    response = client_ana.post(
        reverse("sources:add"), {"url": "https://example.com/feed", "name": "New", "category": "World"}
    )

    assert response.status_code == 200
    assert "already" in str(response.context["form"].errors["url"])
    assert network["calls"] == []
    assert Source.objects.filter(user=ana).count() == 1


def test_add_allows_a_url_another_user_follows(client_ana, ana, bia, network):
    Source.objects.create(user=bia, name="Hers", url="https://example.com/feed", category="Tech")

    client_ana.post(reverse("sources:add"), {"url": "https://example.com/feed", "name": "", "category": "Tech"})

    assert Source.objects.filter(user=ana, url="https://example.com/feed").exists()


def test_add_rejects_get(client_ana):
    assert client_ana.get(reverse("sources:add")).status_code == 405


# ── Catalogue pick ───────────────────────────────────────────────────────────


def test_pick_adds_a_catalogue_source(client_ana, ana, small_catalogue, network):
    response = client_ana.post(reverse("sources:pick"), {"category": "World", "name": "NPR News"})

    assert response.status_code == 302
    source = Source.objects.get(user=ana)
    assert (source.category, source.name, source.url) == ("World", "NPR News", "https://feeds.npr.org/1001/rss.xml")
    assert network["calls"] == []  # the catalogue is trusted


def test_pick_twice_keeps_one_source(client_ana, ana, small_catalogue):
    for _ in range(2):
        client_ana.post(reverse("sources:pick"), {"category": "World", "name": "NPR News"})

    assert Source.objects.filter(user=ana).count() == 1


def test_pick_rejects_entries_not_in_the_catalogue(client_ana, ana, small_catalogue):
    response = client_ana.post(reverse("sources:pick"), {"category": "World", "name": "Evil"})

    assert response.status_code == 404
    assert not Source.objects.filter(user=ana).exists()


# ── Toggle and delete ────────────────────────────────────────────────────────


def test_toggle_flips_active(client_ana, ana):
    source = Source.objects.create(user=ana, name="A", url="https://a.example/rss", category="X")

    client_ana.post(reverse("sources:toggle", args=[source.pk]))
    source.refresh_from_db()
    assert not source.active

    client_ana.post(reverse("sources:toggle", args=[source.pk]))
    source.refresh_from_db()
    assert source.active


def test_delete_removes_the_source(client_ana, ana):
    source = Source.objects.create(user=ana, name="A", url="https://a.example/rss", category="X")

    response = client_ana.post(reverse("sources:delete", args=[source.pk]))

    assert response.status_code == 302
    assert not Source.objects.filter(pk=source.pk).exists()


@pytest.mark.parametrize("name", ["sources:toggle", "sources:delete"])
def test_toggle_and_delete_reject_get(client_ana, ana, name):
    source = Source.objects.create(user=ana, name="A", url="https://a.example/rss", category="X")

    assert client_ana.get(reverse(name, args=[source.pk])).status_code == 405


@pytest.mark.parametrize("name", ["sources:toggle", "sources:delete"])
def test_cannot_touch_another_users_source(client_ana, bia, name):
    hers = Source.objects.create(user=bia, name="Hers", url="https://hers.example/rss", category="X")

    response = client_ana.post(reverse(name, args=[hers.pk]))

    assert response.status_code == 404
    hers.refresh_from_db()
    assert hers.active


# ── The edition follows the changes ──────────────────────────────────────────


def test_edition_sources_follow_the_users_changes(client_ana, ana, bia, small_catalogue, network):
    Source.objects.create(user=bia, name="Hers", url="https://hers.example/rss", category="Tech")

    client_ana.post(reverse("sources:pick"), {"category": "World", "name": "BBC World"})
    client_ana.post(reverse("sources:add"), {"url": "https://example.com/feed", "name": "Ex", "category": "Tech"})
    assert Source.objects.edition_sources(ana) == {
        "Tech": {"Ex": "https://example.com/feed"},
        "World": {"BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    }

    ex = Source.objects.get(user=ana, name="Ex")
    client_ana.post(reverse("sources:toggle", args=[ex.pk]))
    assert Source.objects.edition_sources(ana) == {
        "World": {"BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    }

    bbc = Source.objects.get(user=ana, name="BBC World")
    client_ana.post(reverse("sources:delete", args=[bbc.pk]))
    assert Source.objects.edition_sources(ana) == {}
    assert Source.objects.edition_sources(bia) == {"Tech": {"Hers": "https://hers.example/rss"}}


# ── Starter set ──────────────────────────────────────────────────────────────


def test_add_starter_sources_copies_the_catalogue(ana, small_catalogue):
    created = add_starter_sources(ana)

    assert created == 3
    assert Source.objects.edition_sources(ana) == catalogue.load()


def test_add_starter_sources_skips_what_the_user_has(ana, small_catalogue):
    Source.objects.create(user=ana, name="Mine", url="https://feeds.npr.org/1001/rss.xml", category="Mine", active=False)

    assert add_starter_sources(ana) == 2
    assert add_starter_sources(ana) == 0
    assert Source.objects.get(user=ana, url="https://feeds.npr.org/1001/rss.xml").name == "Mine"


def test_add_starter_sources_can_limit_categories(ana, small_catalogue):
    assert add_starter_sources(ana, categories=["Tech"]) == 1
    assert list(Source.objects.edition_sources(ana)) == ["Tech"]


def test_starter_sources_command(ana, small_catalogue):
    out = StringIO()

    call_command("add_starter_sources", "ana", "--category", "World", stdout=out)

    assert Source.objects.filter(user=ana).count() == 2
    assert "2" in out.getvalue()


def test_starter_sources_command_unknown_user(db, small_catalogue):
    with pytest.raises(CommandError, match="nobody"):
        call_command("add_starter_sources", "nobody")
