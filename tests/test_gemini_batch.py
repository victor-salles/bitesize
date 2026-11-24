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



def test_process_articles_keeps_the_ai_short_title(monkeypatch):
    articles = [
        {"title": "Sonda registra gêiseres de gelo em lua de Saturno", "content": "body", "source": "A"},
        {"title": "Two", "content": "body two", "source": "B"},
    ]
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini.jev_triage, "available", lambda: False)
    seen = []

    def fake_call(instruction, stdin_data, label=""):
        seen.append(instruction)
        return ('[{"id":0,"skip":false,"summary":"Ok.","relevance":70,"short_title":"  Gêiseres em Saturno "},'
                '{"id":1,"skip":false,"summary":"Ok.","relevance":60}]')

    monkeypatch.setattr(gemini, "_call_ai", fake_call)
    out = {a["title"]: a for a in gemini.process_articles(articles, batch_size=2)}

    assert "short_title" in seen[0]
    assert out["Sonda registra gêiseres de gelo em lua de Saturno"]["short_title"] == "Gêiseres em Saturno"
    assert "short_title" not in out["Two"]


@pytest.mark.allow_jev
def test_jev_path_asks_the_writing_model_for_the_short_title(monkeypatch):
    articles = [{"title": "News", "content": "A real story about rates. " * 10, "source": "G1"}]

    def _classify(arts, **kwargs):
        return [{**a, "skip": False, "relevance": 80, "relevance_source": "ai", "tipo": "resumo", "temas": []}
                for a in arts]

    monkeypatch.setattr(gemini.jev_triage, "available", lambda: True)
    monkeypatch.setattr(gemini.jev_triage, "classify_articles", _classify)
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini, "_call_ai",
        lambda instruction, stdin_data, label="": '[{"id":0,"summary":"Rates held.","short_title":"Juros parados"}]',
    )
    (out,) = gemini.process_articles(articles, batch_size=10)
    assert out["short_title"] == "Juros parados"


def test_long_articles_are_marked_and_keep_three_key_points(monkeypatch):
    long_body = "palavra " * 2000
    articles = [
        {"title": "Long", "content": long_body, "source": "A"},
        {"title": "Short", "content": "body two", "source": "B"},
    ]
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini.jev_triage, "available", lambda: False)
    seen = []

    def fake_call(instruction, stdin_data, label=""):
        seen.append((instruction, stdin_data))
        return ('[{"id":0,"skip":false,"summary":"Ok.","relevance":70,'
                '"key_points":["Um.","Dois.","Três.","Quatro."]},'
                '{"id":1,"skip":false,"summary":"Ok.","relevance":60,"key_points":"not a list"}]')

    monkeypatch.setattr(gemini, "_call_ai", fake_call)
    out = {a["title"]: a for a in gemini.process_articles(articles, batch_size=2)}

    instruction, block = seen[0]
    assert "key_points" in instruction
    assert block.count(gemini.LONG_ARTICLE_MARK) == 1
    assert block.index(gemini.LONG_ARTICLE_MARK) < block.index('[1] "Short"')
    assert out["Long"]["key_points"] == ["Um.", "Dois.", "Três."]
    assert "key_points" not in out["Short"]
