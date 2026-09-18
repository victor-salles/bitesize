"""Call Jev once per article and attach skip / relevance / tags."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from config import console, get_settings
from jev_log import write_run
from jev_policy import judgment_from_answers
from jev_questions import article_state, news_questions, tema_nouls
from themes import list_themes
from tags import normalize_tags

MAX_WORKERS = 32


def available() -> bool:
    if not get_settings().jev_triage_enabled:
        return False
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def worker_count(raw: int | None = None) -> int:
    n = get_settings().jev_workers if raw is None else raw
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 4
    return max(1, min(n, MAX_WORKERS))


def flatten_response(response: Any) -> dict[str, Any]:
    temas = {}
    for qid, tema in tema_nouls().items():
        temas[tema] = float(response.nouls[qid].noul)
    tipo = response.choices["tipo"]
    usage = getattr(response, "usage", None)
    usage_payload = None
    if usage is not None:
        usage_payload = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
    probs = getattr(tipo, "probabilities", None)
    if probs is not None and not isinstance(probs, dict):
        try:
            probs = dict(probs)
        except (TypeError, ValueError):
            probs = None
    return {
        "ad": float(response.nouls["ad"].noul),
        "clickbait": float(response.nouls["clickbait"].noul),
        "press_release": float(response.nouls["press_release"].noul),
        "paywall_teaser": float(response.nouls["paywall_teaser"].noul),
        "tipo": tipo.choice,
        "tipo_probabilities": probs,
        "temas": temas,
        "model": getattr(response, "model", None),
        "usage": usage_payload,
    }


def apply_judgment(
    art: dict,
    judgment: dict[str, Any],
    *,
    answers: dict[str, Any] | None = None,
) -> dict:
    out = art.copy()
    out["skip"] = judgment["skip"]
    out["skip_reason"] = judgment.get("skip_reason")
    out["jev"] = {"answers": answers or {}, "judgment": judgment}
    if judgment["skip"]:
        return out
    out["relevance"] = judgment["relevance"]
    out["relevance_source"] = "ai"
    normalize_tags(out, {"tipo": judgment["tipo"], "temas": judgment["temas"]})
    return out


def classify_article(
    art: dict,
    *,
    system_one: Callable[..., Any] | None = None,
) -> dict:
    state = article_state(art)
    questions = news_questions()
    try:
        if system_one is None:
            from typesafe_sdk import TypeSafeClient

            with TypeSafeClient() as client:
                response = client.system_one(state=state, questions=questions)
        else:
            response = system_one(state=state, questions=questions)
        answers = flatten_response(response)
        ranked_ids = [t["id"] for t in list_themes() if t["enabled"]]
        judgment = judgment_from_answers(
            answers,
            min_keep=get_settings().jev_min_keep,
            ranked_ids=ranked_ids,
        )
        return apply_judgment(art, judgment, answers=answers)
    except Exception as exc:
        out = art.copy()
        out["skip"] = False
        out["jev_error"] = f"{type(exc).__name__}: {exc}"
        return out


def classify_articles(
    articles: list[dict],
    *,
    system_one: Callable[..., Any] | None = None,
) -> list[dict]:
    if not articles:
        return []
    workers = min(worker_count(), len(articles))
    out: list[dict | None] = [None] * len(articles)

    def _one(index: int, art: dict) -> tuple[int, dict]:
        return index, classify_article(art, system_one=system_one)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, i, art) for i, art in enumerate(articles)]
        for fut in as_completed(futures):
            i, classified = fut.result()
            out[i] = classified
    rows = [row for row in out if row is not None]
    settings = get_settings()
    run = write_run(rows, min_keep=settings.jev_min_keep, workers=workers)
    console.print(
        f"  Jev run saved: {run['path']} "
        f"({run['kept']} kept, {run['skipped']} skipped, {run['errors']} errors)"
    )
    return rows
