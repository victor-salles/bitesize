from themes import compiled_relevance
from jev_policy import judgment_from_answers
from jev_questions import news_questions


def test_news_questions_omit_keep_and_score_relevance():
    qs = news_questions()
    assert "keep" not in qs
    assert "relevance" not in qs
    assert "ad" in qs
    assert any(k.startswith("tema_") for k in qs)


def test_judgment_compiles_theme_scores():
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.0,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"economia": 1.0, "esportes": 0.0},
    }
    j = judgment_from_answers(answers, min_keep=0, ranked_ids=["economia", "esportes"])
    assert j["skip"] is False
    assert j["relevance"] == compiled_relevance(answers["temas"], ["economia", "esportes"])


def test_judgment_weak_skip_uses_compiled_relevance():
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.0,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"economia": 0.0, "esportes": 0.0},
    }
    j = judgment_from_answers(answers, min_keep=50, ranked_ids=["economia", "esportes"])
    assert j["skip"] is True
    assert j["skip_reason"] == "weak"


def test_judgment_clickbait_penalty_on_compiled_relevance():
    answers = {
        "ad": 0.01,
        "clickbait": 0.9,
        "press_release": 0.0,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"economia": 1.0},
    }
    base = judgment_from_answers(
        {**answers, "clickbait": 0.0}, min_keep=0, ranked_ids=["economia"]
    )["relevance"]
    penalized = judgment_from_answers(answers, min_keep=0, ranked_ids=["economia"])["relevance"]
    assert penalized == max(0, base - 8)


def test_judgment_press_release_penalty_on_compiled_relevance():
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.9,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"economia": 1.0},
    }
    base = judgment_from_answers(
        {**answers, "press_release": 0.0}, min_keep=0, ranked_ids=["economia"]
    )["relevance"]
    penalized = judgment_from_answers(answers, min_keep=0, ranked_ids=["economia"])["relevance"]
    assert penalized == max(0, base - 5)


def test_judgment_tema_apply_threshold():
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.0,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"política": 0.81, "economia": 0.55, "saúde": 0.2},
    }
    ranked = ["política", "economia", "saúde"]
    j = judgment_from_answers(answers, min_keep=0, ranked_ids=ranked)
    assert j["skip"] is False
    assert j["temas"] == ["economia", "política"]


def test_judgment_paywall_teaser_forces_resumo():
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.0,
        "paywall_teaser": 0.8,
        "tipo": "artigo-completo",
        "temas": {"economia": 1.0},
    }
    j = judgment_from_answers(answers, min_keep=0, ranked_ids=["economia"])
    assert j["tipo"] == "resumo"
