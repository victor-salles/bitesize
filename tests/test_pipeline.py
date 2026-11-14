import json
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

    book = epub.read_epub(str(result.epub_path))
    assert book.get_metadata("DC", "language")[0][0].startswith("en")
    assert config._settings is None  # never loaded the global settings


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
