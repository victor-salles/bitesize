from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import jev_log
import jev_triage
from jev_questions import TEMA_NOULS, article_state

pytestmark = pytest.mark.allow_jev


@pytest.fixture(autouse=True)
def jev_json_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")


class FakeNoul:
    def __init__(self, noul):
        self.noul = noul


class FakeScore:
    def __init__(self, score):
        self.score = score
        self.confidence = 1.0


class FakeChoice:
    def __init__(self, choice):
        self.choice = choice


def _response(*, ad=0.05, keep=0.85, clickbait=0.1, press=0.1, paywall=0.1, relevance=3.0, tipo="artigo-completo", tema_hits=None):
    tema_hits = tema_hits or {"economia": 0.8}
    nouls = {
        "ad": FakeNoul(ad),
        "keep": FakeNoul(keep),
        "clickbait": FakeNoul(clickbait),
        "press_release": FakeNoul(press),
        "paywall_teaser": FakeNoul(paywall),
    }
    for qid, tema in TEMA_NOULS.items():
        nouls[qid] = FakeNoul(tema_hits.get(tema, 0.05))
    return SimpleNamespace(
        nouls=nouls,
        scores={"relevance": FakeScore(relevance)},
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


def test_article_state_truncates_long_body():
    art = {"title": "T", "content": "x" * 9000, "source": "G1", "category": "Brasil"}
    state = article_state(art)
    assert len(state["body"]) == 8000
    assert state["title"] == "T"


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
    out = jev_triage.classify_article(
        art,
        system_one=lambda **kwargs: _response(relevance=3.0, tipo="artigo-completo"),
    )
    assert out["skip"] is False
    assert out["relevance"] == 75
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
    assert loaded["items"][0]["jev"]["answers"]["keep"] > 0
