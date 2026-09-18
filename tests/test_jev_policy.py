"""Jev news judgments → skip, relevance, tipo, temas. No TypeSafe calls."""

from jev_policy import judgment_from_answers, relevance_int


def _answers(**overrides):
    temas = {t: 0.1 for t in ("política", "saúde", "economia", "tecnologia", "mundo")}
    temas.update(overrides.pop("temas", {}))
    base = {
        "ad": 0.05,
        "keep": 0.8,
        "clickbait": 0.1,
        "press_release": 0.1,
        "paywall_teaser": 0.1,
        "relevance": 3.0,
        "tipo": "artigo-completo",
        "temas": temas,
    }
    base.update(overrides)
    return base


def test_relevance_int_maps_score_span_to_0_100():
    assert relevance_int(0.0) == 0
    assert relevance_int(4.0) == 100
    assert relevance_int(2.0) == 50


def test_high_ad_score_skips_article():
    out = judgment_from_answers(_answers(ad=0.9), min_keep=0)
    assert out["skip"] is True
    assert out["skip_reason"] == "ad"


def test_weak_keep_skips_only_when_threshold_set():
    answers = _answers(keep=0.2)
    kept = judgment_from_answers(answers, min_keep=0)
    dropped = judgment_from_answers(answers, min_keep=40)
    assert kept["skip"] is False
    assert dropped["skip"] is True
    assert dropped["skip_reason"] == "weak"


def test_temas_above_threshold_are_kept():
    out = judgment_from_answers(
        _answers(temas={"política": 0.81, "economia": 0.55, "saúde": 0.2}),
        min_keep=0,
    )
    assert out["skip"] is False
    assert out["temas"] == ["economia", "política"]


def test_paywall_teaser_forces_resumo():
    out = judgment_from_answers(
        _answers(tipo="artigo-completo", paywall_teaser=0.8),
        min_keep=0,
    )
    assert out["tipo"] == "resumo"


def test_clickbait_lowers_relevance():
    clean = judgment_from_answers(_answers(clickbait=0.1, relevance=3.0), min_keep=0)
    bait = judgment_from_answers(_answers(clickbait=0.85, relevance=3.0), min_keep=0)
    assert bait["relevance"] < clean["relevance"]
