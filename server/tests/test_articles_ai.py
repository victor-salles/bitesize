"""Server AI: Gemini client, daily cap and the shared article cache."""

import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

import feed
import pipeline
from articles.cache import DatabaseArticleCache, text_hash
from articles.gemini import GeminiClient
from articles.models import AIUsage
from core.models import Article
from pipeline import EditionConfig, build_edition
from settings_store import Settings

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Rates hold steady</title><link>https://example.com/a</link>
<description>Short snippet.</description></item>
<item><title>Sneaker sale</title><link>https://example.com/ad</link>
<description>Buy now.</description></item>
</channel></rss>"""

BODY = "The central bank kept rates unchanged on Tuesday. " * 10


class FakeModels:
    """Stands in for genai.Client().models: answers like Gemini would."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "instruction": config.system_instruction})
        if self.fail:
            raise RuntimeError("boom")
        instruction = config.system_instruction
        if "section front page" in instruction:
            text = json.dumps({"headline": "Rates", "editorial": "Calm.", "top_stories": []})
        elif "editor-in-chief" in instruction:
            text = json.dumps({"headline": "Today", "editorial": "Calm.", "highlights": []})
        else:
            rows = [
                {"id": i, "skip": "Sneaker" in line, "summary": "Held. Calm.", "relevance": 80 - i}
                for i, line in enumerate(l for l in contents.split("\n") if l.startswith("["))
            ]
            text = json.dumps(rows)
        return SimpleNamespace(text=text)

    def summary_calls(self):
        return [c for c in self.calls if "article snippets" in c["instruction"]]


def make_client(models=None, *, api_key="test-key", cap=100):
    return GeminiClient(
        api_key=api_key,
        model="gemini-test",
        daily_cap=cap,
        sdk=SimpleNamespace(models=models or FakeModels()),
    )


# ── GeminiClient ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_call_sends_instruction_and_data_to_the_configured_model():
    models = FakeModels()
    client = make_client(models)

    out = client.call("You are a newspaper editor for X. section front page", "[0] A", label="cover")

    assert json.loads(out)["headline"] == "Rates"
    assert models.calls[0]["model"] == "gemini-test"
    assert models.calls[0]["contents"] == "[0] A"
    assert AIUsage.objects.get(day=timezone.localdate()).requests == 1


@pytest.mark.django_db
def test_missing_key_is_unavailable_and_never_calls(settings):
    settings.GEMINI_API_KEY = ""
    models = FakeModels()
    client = GeminiClient.from_settings(sdk=SimpleNamespace(models=models))

    assert client.available() is False
    assert client.call("x", "y") is None
    assert models.calls == []


@pytest.mark.django_db
def test_from_settings_reads_model_and_cap(settings):
    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_MODEL = "gemini-other"
    settings.GEMINI_DAILY_REQUEST_CAP = 7

    client = GeminiClient.from_settings(sdk=SimpleNamespace(models=FakeModels()))

    assert (client.model, client.daily_cap, client.available()) == ("gemini-other", 7, True)


@pytest.mark.django_db
def test_cap_reached_makes_the_client_unavailable():
    models = FakeModels()
    client = make_client(models, cap=2)

    assert client.call("a", "b") is not None
    assert client.call("a", "b") is not None
    assert client.available() is False
    assert client.call("a", "b") is None
    assert len(models.calls) == 2


@pytest.mark.django_db
def test_cap_resets_the_next_day():
    AIUsage.objects.create(day=date(2000, 1, 1), requests=99)

    assert make_client(cap=2).available() is True


@pytest.mark.django_db
def test_api_error_returns_none_without_leaking_the_key(capsys, caplog):
    client = make_client(FakeModels(fail=True), api_key="super-secret-key")

    assert client.call("a", "b", label="x") is None
    out = capsys.readouterr()
    assert "super-secret-key" not in out.out + out.err + caplog.text


# ── DatabaseArticleCache ─────────────────────────────────────────────────────


ART = {"url": "https://example.com/a", "title": "Rates hold", "source": "Wire", "content": BODY}
RESULT = {"summary": "Held. Calm.", "relevance": 72, "tipo": "artigo-completo", "temas": ["economia"]}


@pytest.mark.django_db
def test_cache_miss_then_hit():
    cache = DatabaseArticleCache()
    assert cache.get(ART, "en") is None

    cache.put(ART, "en", RESULT)

    assert cache.get(ART, "en") == {**RESULT, "skip": False}
    row = Article.objects.get(url=ART["url"], language="en")
    assert (row.title, row.source, row.score, row.text_length) == ("Rates hold", "Wire", 72, len(BODY))
    assert row.text_hash == text_hash(ART)


@pytest.mark.django_db
def test_cache_keeps_the_optional_ai_fields_and_reads_rows_without_them():
    cache = DatabaseArticleCache()
    cache.put(ART, "en", {**RESULT, "short_title": "Rates hold"})
    assert cache.get(ART, "en") == {**RESULT, "short_title": "Rates hold", "skip": False}

    # A row written before short titles existed, shared by every user: no field, no error.
    Article.objects.filter(url=ART["url"]).update(tags={"tipo": "artigo-completo", "temas": ["economia"]})
    assert cache.get(ART, "en") == {**RESULT, "skip": False}


@pytest.mark.django_db
def test_cache_is_invalidated_when_the_text_changes():
    cache = DatabaseArticleCache()
    cache.put(ART, "en", RESULT)

    changed = {**ART, "content": BODY + " Update: rates were cut."}
    assert cache.get(changed, "en") is None

    cache.put(changed, "en", {**RESULT, "summary": "Cut."})
    assert Article.objects.filter(url=ART["url"]).count() == 1
    assert cache.get(changed, "en")["summary"] == "Cut."


@pytest.mark.django_db
def test_cache_is_per_language():
    cache = DatabaseArticleCache()
    cache.put(ART, "en", RESULT)

    assert cache.get(ART, "pt-BR") is None


@pytest.mark.django_db
def test_cache_remembers_skipped_ads():
    cache = DatabaseArticleCache()
    cache.put(ART, "en", {"skip": True})

    assert cache.get(ART, "en") == {"skip": True}


# ── Two users, one AI call ───────────────────────────────────────────────────


@pytest.fixture
def same_feed(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url, quiet=False: RSS)
    monkeypatch.setattr(pipeline, "fetch_article_content", lambda url: BODY)


def _build_for(user, client, tmp_path):
    return build_edition(
        EditionConfig(
            sources={"Economy": {"Wire": "https://feeds.example.com/rss"}},
            output_dir=tmp_path / user.username,
            settings=Settings(ai_backend="does-not-exist"),
            language=user.profile.language,
            ai=client,
            article_cache=DatabaseArticleCache(),
            now=datetime(2026, 11, 14, 7, 0),
        )
    )


@pytest.mark.django_db
def test_two_users_with_the_same_feed_share_one_ai_call_per_article(tmp_path, same_feed):
    ana = User.objects.create_user("ana")
    bia = User.objects.create_user("bia")
    models = FakeModels()

    first = _build_for(ana, make_client(models), tmp_path)
    second = _build_for(bia, make_client(models), tmp_path)

    assert len(models.summary_calls()) == 1
    assert first.kept_count == second.kept_count == 1  # the ad stays skipped
    assert Article.objects.count() == 2
    assert Article.objects.get(url="https://example.com/a").summary == "Held. Calm."


@pytest.mark.django_db
def test_cap_reached_falls_back_to_the_no_summary_edition(tmp_path, same_feed):
    ana = User.objects.create_user("ana")
    models = FakeModels()

    result = _build_for(ana, make_client(models, cap=0), tmp_path)

    assert models.calls == []
    assert result.epub_path is not None and result.epub_path.exists()
    assert result.kept_count == 2  # nothing filtered without AI
    assert Article.objects.count() == 0  # fallback scores are not cached


# ── Factories for the edition build ──────────────────────────────────────────


@pytest.mark.django_db
def test_factories_give_the_configured_client_and_the_database_cache(settings):
    from articles.services import get_article_cache, get_server_ai_client

    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_MODEL = "gemini-other"

    client = get_server_ai_client()

    assert isinstance(client, GeminiClient) and client.model == "gemini-other"
    assert isinstance(get_article_cache(), DatabaseArticleCache)


@pytest.mark.django_db
def test_cache_stores_an_empty_summary_when_the_ai_returns_none():
    # Seen in production on 2026-11-23: the AI scored an article but sent
    # "summary": null, and the NOT NULL column failed the whole edition.
    cache = DatabaseArticleCache()

    cache.put(ART, "en", {**RESULT, "summary": None, "temas": None})

    assert cache.get(ART, "en") == {**RESULT, "summary": "", "temas": [], "skip": False}
