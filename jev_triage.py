"""Call Jev once per article and attach skip / relevance / tags."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from config import get_settings
from jev_policy import judgment_from_answers
from jev_questions import TEMA_NOULS, article_state, news_questions
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
    for qid, tema in TEMA_NOULS.items():
        temas[tema] = float(response.nouls[qid].noul)
    return {
        "ad": float(response.nouls["ad"].noul),
        "keep": float(response.nouls["keep"].noul),
        "clickbait": float(response.nouls["clickbait"].noul),
        "press_release": float(response.nouls["press_release"].noul),
        "paywall_teaser": float(response.nouls["paywall_teaser"].noul),
        "relevance": float(response.scores["relevance"].score),
        "tipo": response.choices["tipo"].choice,
        "temas": temas,
    }


def apply_judgment(art: dict, judgment: dict[str, Any]) -> dict:
    out = art.copy()
    out["skip"] = judgment["skip"]
    out["skip_reason"] = judgment.get("skip_reason")
    out["jev"] = {
        "keep": judgment.get("keep"),
        "ad": judgment.get("ad"),
        "clickbait": judgment.get("clickbait"),
        "press_release": judgment.get("press_release"),
        "paywall_teaser": judgment.get("paywall_teaser"),
    }
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
        judgment = judgment_from_answers(
            flatten_response(response),
            min_keep=get_settings().jev_min_keep,
        )
        return apply_judgment(art, judgment)
    except Exception:
        out = art.copy()
        out["skip"] = False
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
    return [row for row in out if row is not None]
