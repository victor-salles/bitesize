import json
import socket
from datetime import datetime

import pytest
from ebooklib import epub

import config
import feed
import pipeline
import settings_store
from pipeline import EditionConfig, ExtraSection, build_edition
from settings_store import Settings

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Rates hold steady</title><link>https://example.com/a</link>
<description>Short snippet.</description></item>
<item><title>Sneaker sale</title><link>https://example.com/ad</link>
<description>Buy now.</description></item>
<item><title>Third story</title><link>https://example.com/c</link>
<description>Another snippet.</description></item>
</channel></rss>"""

BODY = "The central bank kept rates unchanged on Tuesday. " * 10


class FakeAI:
    def __init__(self):
        self.labels = []

    def available(self):
        return True

    def call(self, instruction, stdin_data, label=""):
        self.labels.append(label)
        if label.startswith("section-cover"):
            return json.dumps({
                "headline": "Rates hold",
                "editorial": "Banks wait.",
                "top_stories": [{"title": "Rates hold steady", "one_liner": "No change."}],
            })
        if label.startswith("global-cover"):
            return json.dumps({"headline": "Today", "editorial": "Calm.", "highlights": []})
        if "JSON array" in instruction and "[0]" in stdin_data:
            rows = []
            for i, line in enumerate(l for l in stdin_data.split("\n") if l.startswith("[")):
                rows.append({
                    "id": i,
                    "skip": "Sneaker" in line,
                    "summary": "The bank held rates. Markets were calm.",
                    "relevance": 80 - i,
                    "temas": ["economia"],
                })
            return json.dumps(rows)
        return None


@pytest.fixture
def no_global_config(monkeypatch):
    """Fail loudly if anything reaches the database-backed settings."""
    monkeypatch.setattr(config, "_settings", None)

    def _boom(*a, **k):
        raise AssertionError("build_edition read data/bitesize.db")

    monkeypatch.setattr(settings_store, "init_db", _boom)
    monkeypatch.setattr(settings_store, "load_settings", _boom)
    monkeypatch.setattr(config, "load_env", _boom)


def test_build_edition_from_in_memory_inputs(tmp_path, monkeypatch, no_global_config):
    fetched_urls = []

    def fake_download(url, quiet=False):
        fetched_urls.append(url)
        return RSS

    monkeypatch.setattr(feed, "_download_url", fake_download)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)

    ai = FakeAI()
    result = build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path / "out",
            settings=Settings(ai_backend="does-not-exist"),
            language="en",
            max_articles_per_feed=2,
            ai=ai,
            extra_sections=[
                ExtraSection(
                    "Calendar",
                    [{"title": "Standup", "content": BODY, "summary": "", "source": "Cal",
                      "url": "", "category": "Calendar"}],
                    lambda arts: {"headline": "Your day"},
                )
            ],
            now=datetime(2026, 11, 13, 7, 0),
        )
    )

    assert fetched_urls == ["https://feeds.example.com/rss"]
    assert result.epub_path is not None and result.epub_path.exists()
    assert result.epub_path.parent == tmp_path / "out"
    assert result.raw_count == 2  # max_articles_per_feed override
    assert result.full_text_count == 2
    assert result.kept_count == 1  # the ad was skipped
    assert result.section_counts == {"Economy": 1, "Calendar": 1}
    assert result.article_count == 2
    assert any(l.startswith("section-cover:Economy") for l in ai.labels)
    assert (tmp_path / "out" / "logs" / "paywall-stats.log").exists()

    assert result.topic_counts == {"economia": 1}

    book = epub.read_epub(str(result.epub_path))
    assert book.get_metadata("DC", "language")[0][0].startswith("en")
    assert "November 13, 2026" in book.get_metadata("DC", "title")[0][0]  # config.now, not the clock
    assert config._settings is None  # never loaded the global settings


def test_build_edition_passes_the_edition_history_to_the_epub(tmp_path, monkeypatch, no_global_config):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)
    seen = []
    monkeypatch.setattr(pipeline, "generate_epub", lambda *args, meta: seen.append(meta))

    build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path,
            settings=Settings(ai_backend="does-not-exist"),
            ai=FakeAI(),
            now=datetime(2026, 11, 13, 7, 0),
            edition_number=12,
            previous_topic_counts={"economia": 3},
        )
    )

    (meta,) = seen
    assert meta.now == datetime(2026, 11, 13, 7, 0)
    assert meta.edition_number == 12
    assert meta.previous_topic_counts == {"economia": 3}
    assert meta.cover_style == "numero"  # cover B is the default


def test_cover_style_comes_from_settings_unless_the_config_overrides_it(tmp_path, monkeypatch, no_global_config):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)
    seen = []
    monkeypatch.setattr(pipeline, "generate_epub", lambda *args, meta: seen.append(meta.cover_style))

    for override in (None, "jornal-invert"):
        build_edition(
            EditionConfig(
                sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
                output_dir=tmp_path,
                settings=Settings(ai_backend="does-not-exist", cover_style="jornal"),
                ai=FakeAI(),
                cover_style=override,
            )
        )

    assert seen == ["jornal", "jornal-invert"]


def test_build_edition_without_readable_articles_writes_nothing(
    tmp_path, monkeypatch, no_global_config
):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: None)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: "")

    result = build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path,
            ai=FakeAI(),
        )
    )

    assert result.epub_path is None
    assert result.raw_count == 0
    assert not list(tmp_path.glob("*.epub"))


class MemoryCache:
    """In-memory ArticleCache keyed by (url, language)."""

    def __init__(self):
        self.rows = {}

    def get(self, art, language):
        return self.rows.get((art["url"], language))

    def put(self, art, language, result):
        self.rows[(art["url"], language)] = result


def _edition(tmp_path, ai, cache, language="en"):
    return build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path,
            settings=Settings(ai_backend="does-not-exist"),
            language=language,
            ai=ai,
            article_cache=cache,
            now=datetime(2026, 11, 13, 7, 0),
        )
    )


def _summary_calls(ai):
    return [l for l in ai.labels if l == ""]


def test_article_cache_reuses_summaries_and_skips_across_editions(
    tmp_path, monkeypatch, no_global_config
):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)
    cache = MemoryCache()

    first_ai = FakeAI()
    first = _edition(tmp_path / "a", first_ai, cache)
    second_ai = FakeAI()
    second = _edition(tmp_path / "b", second_ai, cache)

    assert len(_summary_calls(first_ai)) == 1
    assert _summary_calls(second_ai) == []
    assert cache.rows[("https://example.com/ad", "en")] == {"skip": True}
    hit = cache.rows[("https://example.com/a", "en")]
    assert hit["summary"] == "The bank held rates. Markets were calm."
    assert {"relevance", "tipo", "temas"} <= hit.keys()
    assert first.kept_count == second.kept_count == 2


def test_article_cache_is_per_language(tmp_path, monkeypatch, no_global_config):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)
    cache = MemoryCache()

    _edition(tmp_path / "en", FakeAI(), cache, language="en")
    pt_ai = FakeAI()
    _edition(tmp_path / "pt", pt_ai, cache, language="pt-BR")

    assert len(_summary_calls(pt_ai)) == 1


def test_article_cache_does_not_store_fallback_results(tmp_path, monkeypatch, no_global_config):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)

    class DownAI(FakeAI):
        def available(self):
            return False

    cache = MemoryCache()
    result = _edition(tmp_path, DownAI(), cache)

    assert cache.rows == {}
    assert result.kept_count == 3  # no-summary edition keeps everything


# ── Internal addresses ───────────────────────────────────────────────────────

INTERNAL_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Rates hold steady</title><link>https://example.com/a</link>
<description>Short snippet.</description></item>
<item><title>Cloud metadata</title><link>http://metadata.internal/latest/</link>
<description>Looks like news.</description></item>
</channel></rss>"""

ARTICLE_HTML = (
    "<html><head><title>Rates hold steady</title></head><body><article><h1>Rates hold steady</h1>"
    + "".join(f"<p>{BODY}</p>" for _ in range(3))
    + "</article></body></html>"
).encode()


class FakeResponse:
    def __init__(self, body):
        self.status_code = 200
        self.headers = {}
        self.body = body

    def iter_content(self, chunk_size=1):
        yield self.body

    def close(self):
        pass


@pytest.fixture
def fake_network(monkeypatch):
    """Serve the feed and the public article through safe_fetch; record every URL opened."""
    import safe_fetch

    pages = {"https://feeds.example.com/rss": INTERNAL_RSS, "https://example.com/a": ARTICLE_HTML}
    ips = {"metadata.internal": "169.254.169.254"}
    opened = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        ip = ips.get(host, "93.184.215.14")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    def fake_open(_session, target, **kwargs):
        opened.append(target.url)
        return FakeResponse(pages.get(target.url, b""))

    monkeypatch.setattr(safe_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(safe_fetch, "_open", fake_open)
    return opened


def test_build_edition_skips_an_article_on_an_internal_address(tmp_path, fake_network, no_global_config):
    result = build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path,
            settings=Settings(ai_backend="does-not-exist"),
            language="en",
            ai=FakeAI(),
            now=datetime(2026, 11, 13, 7, 0),
        )
    )

    assert not any("metadata.internal" in url for url in fake_network)
    assert result.epub_path is not None and result.epub_path.exists()
    assert (result.raw_count, result.full_text_count, result.article_count) == (1, 1, 1)
    book = epub.read_epub(str(result.epub_path))
    pages = b"".join(item.get_content() for item in book.get_items())
    assert b"Rates hold steady" in pages
    assert b"Cloud metadata" not in pages


def test_article_cache_carries_the_short_title_and_tolerates_rows_without_it(monkeypatch):
    cache = MemoryCache()
    cache.rows[("https://example.com/old", "en")] = {
        "summary": "Old row.", "relevance": 50, "tipo": "resumo", "temas": [],
    }
    fresh = {"url": "https://example.com/new", "title": "New story", "content": BODY}

    def fake_process(articles):
        return [{**art, "summary": "S.", "relevance": 70, "relevance_source": "ai", "tipo": "resumo",
                 "temas": [], "short_title": "New"} for art in articles]

    monkeypatch.setattr(pipeline, "process_articles", fake_process)
    with config.use_settings(Settings(ai_language="en")):
        out = pipeline._process_articles(
            [{"url": "https://example.com/old", "title": "Old story", "content": BODY}, fresh], cache
        )

    by_url = {art["url"]: art for art in out}
    assert "short_title" not in by_url["https://example.com/old"]
    assert by_url["https://example.com/new"]["short_title"] == "New"
    assert cache.rows[("https://example.com/new", "en")]["short_title"] == "New"
