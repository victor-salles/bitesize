import pytest

import feed
import safe_fetch
from config import use_settings
from settings_store import Settings


SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test</title>
<item><title>Story One</title><link>https://example.com/1</link>
<description><![CDATA[<p>Body one</p>]]></description></item>
</channel></rss>"""


def test_fetch_feed_uses_downloaded_bytes(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url: SAMPLE_RSS)
    articles = feed.fetch_feed("Test Source", "https://example.com/feed.xml")
    assert len(articles) == 1
    assert articles[0]["title"] == "Story One"
    assert articles[0]["source"] == "Test Source"


def test_fetch_feed_returns_empty_when_download_fails(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url: None)
    articles = feed.fetch_feed("Test Source", "https://example.com/feed.xml")
    assert articles == []


def test_fetch_feed_fail_soft_false_raises_when_download_fails(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url: None)
    try:
        feed.fetch_feed(
            "Test Source",
            "https://example.com/feed.xml",
            fail_soft=False,
        )
    except RuntimeError as exc:
        assert "https://example.com/feed.xml" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_download_url_fetches_through_safe_fetch_with_the_settings(monkeypatch):
    calls = []

    def fake_fetch(url, **kwargs):
        calls.append((url, kwargs))
        return b"ok"

    monkeypatch.setattr(feed.safe_fetch, "fetch", fake_fetch)
    with use_settings(Settings(feed_timeout=9, user_agent="ua", allow_private_addresses=True)):
        assert feed._download_url("https://example.com/rss") == b"ok"

    assert calls == [("https://example.com/rss", {"timeout": 9, "user_agent": "ua", "allow_private": True})]


def test_download_url_returns_none_when_the_site_fails(monkeypatch):
    def fake_fetch(url, **kwargs):
        raise safe_fetch.FetchError(safe_fetch.Reason.TIMEOUT, url)

    monkeypatch.setattr(feed.safe_fetch, "fetch", fake_fetch)
    with use_settings(Settings()):
        assert feed._download_url("https://example.com/rss", quiet=True) is None


def test_download_url_raises_when_the_address_is_blocked(monkeypatch):
    def fake_fetch(url, **kwargs):
        raise safe_fetch.FetchError(safe_fetch.Reason.PRIVATE, url)

    monkeypatch.setattr(feed.safe_fetch, "fetch", fake_fetch)
    with use_settings(Settings()), pytest.raises(safe_fetch.FetchError) as excinfo:
        feed._download_url("http://10.0.0.5/rss")

    assert excinfo.value.reason is safe_fetch.Reason.PRIVATE


def test_fetch_feed_skips_a_feed_on_a_blocked_address(monkeypatch):
    def fake_download(url, quiet=False):
        raise safe_fetch.FetchError(safe_fetch.Reason.PRIVATE, url)

    monkeypatch.setattr(feed, "_download_url", fake_download)
    with use_settings(Settings()):
        assert feed.fetch_feed("Internal", "http://10.0.0.5/rss") == []
