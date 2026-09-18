from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import jev_log
import jev_triage
from themes import compiled_relevance, list_themes
from jev_questions import SNIPPET_CHARS, article_state, tema_nouls

pytestmark = pytest.mark.allow_jev


@pytest.fixture(autouse=True)
def jev_json_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")


class FakeNoul:
    def __init__(self, noul):
        self.noul = noul


class FakeChoice:
    def __init__(self, choice):
        self.choice = choice


def _response(*, ad=0.05, clickbait=0.1, press=0.1, paywall=0.1, tipo="artigo-completo", tema_hits=None):
    tema_hits = tema_hits or {"economia": 0.8}
    nouls = {
        "ad": FakeNoul(ad),
        "clickbait": FakeNoul(clickbait),
        "press_release": FakeNoul(press),
        "paywall_teaser": FakeNoul(paywall),
    }
    for qid, tema in tema_nouls().items():
        nouls[qid] = FakeNoul(tema_hits.get(tema, 0.05))
    return SimpleNamespace(
        nouls=nouls,
        scores={},
        choices={"tipo": FakeChoice(tipo)},
    )


def test_available_needs_flag_and_api_key(monkeypatch):
    settings = MagicMock(jev_triage_enabled=False)
    monkeypatch.setattr(jev_triage, "get_settings", lambda: settings)
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_test")
    assert jev_triage.available() is False

    settings.jev_triage_enabled = True
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert jev_triage.available() is False

    monkeypatch.setenv("TYPESAFE_API_KEY", "ts_test")
    assert jev_triage.available() is True


def test_article_state_sends_snippet_not_full_body():
    art = {
        "title": "Selic",
        "content": "O Banco Central manteve a taxa. " * 400,
        "source": "G1",
        "category": "Brasil",
        "link": "https://example.com/selic",
    }
    state = article_state(art)
    assert "body" not in state
    assert "url" not in state
    assert "category" not in state
    assert set(state) == {"title", "source", "snippet", "body_chars"}
    assert state["title"] == "Selic"
    assert state["source"] == "G1"
    assert len(state["snippet"]) <= SNIPPET_CHARS
    assert state["body_chars"] == len(art["content"].strip())
    assert state["snippet"].startswith("O Banco Central")


def test_classify_article_passes_snippet_state(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "get_settings",
        lambda: MagicMock(jev_triage_enabled=True, jev_min_keep=0, jev_workers=2),
    )
    seen = {}

    def capture(*, state, questions):
        seen["state"] = state
        return _response()

    long_body = "word " * 2000
    jev_triage.classify_article(
        {"title": "T", "content": long_body, "source": "G1"},
        system_one=capture,
    )
    assert "body" not in seen["state"]
    assert len(seen["state"]["snippet"]) <= SNIPPET_CHARS
    assert seen["state"]["body_chars"] == len(long_body.strip())


def test_classify_article_skips_ads(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "get_settings",
        lambda: MagicMock(jev_triage_enabled=True, jev_min_keep=0, jev_workers=2),
    )
    art = {"title": "Buy now", "content": "Sale 50% off sneakers.", "source": "Shop"}
    out = jev_triage.classify_article(
        art,
        system_one=lambda **kwargs: _response(ad=0.95),
    )
    assert out["skip"] is True
    assert out["skip_reason"] == "ad"
    assert out["jev"]["answers"]["ad"] >= 0.9


def test_classify_article_sets_relevance_and_temas(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "get_settings",
        lambda: MagicMock(jev_triage_enabled=True, jev_min_keep=0, jev_workers=2),
    )
    art = {
        "title": "Selic",
        "content": "O Banco Central manteve a taxa. " * 20,
        "source": "G1",
    }
    tema_hits = {"economia": 0.8}
    out = jev_triage.classify_article(
        art,
        system_one=lambda **kwargs: _response(tipo="artigo-completo", tema_hits=tema_hits),
    )
    ranked = [t["id"] for t in list_themes() if t["enabled"]]
    assert out["skip"] is False
    temas = out["jev"]["answers"]["temas"]
    assert out["relevance"] == compiled_relevance(temas, ranked)
    assert out["relevance_source"] == "ai"
    assert "economia" in out["temas"]
    assert out["tipo"] in {"resumo", "artigo-completo"}


def test_classify_articles_keeps_order(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "get_settings",
        lambda: MagicMock(jev_triage_enabled=True, jev_min_keep=0, jev_workers=4),
    )
    arts = [
        {"title": "A", "content": "aaaa", "source": "1"},
        {"title": "B", "content": "bbbb", "source": "2"},
    ]
    out = jev_triage.classify_articles(
        arts,
        system_one=lambda **kwargs: _response(),
    )
    assert [a["title"] for a in out] == ["A", "B"]
    listed = jev_log.list_runs()
    assert len(listed) == 1
    loaded = jev_log.load_run(listed[0]["id"])
    assert [item["title"] for item in loaded["items"]] == ["A", "B"]
    assert loaded["items"][0]["jev"]["answers"]["ad"] >= 0
    assert "keep" not in loaded["items"][0]["jev"]["answers"]
