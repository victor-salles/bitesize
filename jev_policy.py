"""Turn Jev scores into digest decisions. Thresholds live here, not in the model."""

from __future__ import annotations

from typing import Any

from tags import TEMAS, TIPOS

RELEVANCE_LEVELS = 5  # Score criteria 0..4

THRESHOLDS = {
    "ad_skip": 0.65,
    "tema_apply": 0.50,
    "clickbait_penalty": 0.60,
    "press_release_penalty": 0.60,
    "paywall_tipo": 0.65,
    "clickbait_delta": 8,
    "press_release_delta": 5,
}


def relevance_int(score: float) -> int:
    """Map a 0..(levels-1) Score onto 0–100."""
    span = RELEVANCE_LEVELS - 1
    try:
        raw = float(score)
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, int(round(raw / span * 100))))


def judgment_from_answers(
    answers: dict[str, Any],
    *,
    min_keep: int = 0,
) -> dict[str, Any]:
    """Map one System One answer dict to skip / relevance / tipo / temas."""
    ad = float(answers.get("ad") or 0)
    keep = float(answers.get("keep") or 0)
    clickbait = float(answers.get("clickbait") or 0)
    press = float(answers.get("press_release") or 0)
    paywall = float(answers.get("paywall_teaser") or 0)

    if ad >= THRESHOLDS["ad_skip"]:
        return {
            "skip": True,
            "skip_reason": "ad",
            "relevance": 0,
            "tipo": "resumo",
            "temas": [],
            "keep": keep,
            "ad": ad,
        }

    if min_keep > 0 and keep * 100 < min_keep:
        return {
            "skip": True,
            "skip_reason": "weak",
            "relevance": 0,
            "tipo": "resumo",
            "temas": [],
            "keep": keep,
            "ad": ad,
        }

    relevance = relevance_int(answers.get("relevance", 0))
    if clickbait >= THRESHOLDS["clickbait_penalty"]:
        relevance = max(0, relevance - THRESHOLDS["clickbait_delta"])
    if press >= THRESHOLDS["press_release_penalty"]:
        relevance = max(0, relevance - THRESHOLDS["press_release_delta"])

    tipo = answers.get("tipo")
    if tipo not in TIPOS:
        tipo = "artigo-completo"
    if paywall >= THRESHOLDS["paywall_tipo"]:
        tipo = "resumo"

    raw_temas = answers.get("temas") or {}
    temas = sorted(
        t
        for t in TEMAS
        if float(raw_temas.get(t) or 0) >= THRESHOLDS["tema_apply"]
    )

    return {
        "skip": False,
        "skip_reason": None,
        "relevance": relevance,
        "tipo": tipo,
        "temas": temas,
        "keep": keep,
        "ad": ad,
        "clickbait": clickbait,
        "press_release": press,
        "paywall_teaser": paywall,
    }
