from unittest.mock import MagicMock, patch

import pytest

import gemini


def test_process_articles_keeps_missing_batch_ids(monkeypatch):
    articles = [
        {"title": "One", "content": "body one", "source": "A"},
        {"title": "Two", "content": "body two", "source": "B"},
    ]
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini.jev_triage, "available", lambda: False)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": '[{"id":0,"skip":false,"summary":"Ok.","relevance":70}]',
    )
    out = gemini.process_articles(articles, batch_size=2)
    assert len(out) == 2
    titles = {a["title"] for a in out}
    assert titles == {"One", "Two"}


@pytest.mark.allow_jev
def test_process_articles_jev_filters_ads_and_summarizes(monkeypatch):
    articles = [
        {"title": "Ad", "content": "Buy sneakers", "source": "Shop"},
        {"title": "News", "content": "A real story about rates. " * 10, "source": "G1"},
    ]

    def _classify(arts, **kwargs):
        out = []
        for art in arts:
            a = art.copy()
            if art["title"] == "Ad":
                a["skip"] = True
                a["skip_reason"] = "ad"
            else:
                a["skip"] = False
                a["relevance"] = 80
                a["relevance_source"] = "ai"
                a["tipo"] = "artigo-completo"
                a["temas"] = ["economia"]
            out.append(a)
        return out

    monkeypatch.setattr(gemini.jev_triage, "available", lambda: True)
    monkeypatch.setattr(gemini.jev_triage, "classify_articles", _classify)
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": '[{"id":0,"summary":"Rates held. Markets paused."}]',
    )
    out = gemini.process_articles(articles, batch_size=10)
    assert len(out) == 1
    assert out[0]["title"] == "News"
    assert out[0]["relevance"] == 80
    assert out[0]["summary"] == "Rates held. Markets paused."

