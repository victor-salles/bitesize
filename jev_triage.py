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
GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh"
GATEWAY_EVALUATE_PATH = "/v1/evaluate"


def _api_key() -> str:
    for env in ("TYPESAFE_API_KEY", "AI_GATEWAY_API_KEY"):
        value = os.environ.get(env, "").strip()
        if value:
            return value
    return ""


def client_kwargs() -> dict[str, str]:
    key = _api_key()
    kwargs: dict[str, str] = {"api_key": key}
    base = os.environ.get("TYPESAFE_BASE_URL", "").strip()
    if not base and key.startswith("vck_"):
        base = GATEWAY_BASE_URL
    if base:
        kwargs["base_url"] = base.rstrip("/")
    return kwargs


def uses_gateway() -> bool:
    return "ai-gateway.vercel.sh" in client_kwargs().get("base_url", "")


def gateway_model() -> str:
    model = os.environ.get("TYPESAFE_DEFAULT_MODEL", "").strip() or "typesafe-ai/jev"
    if "/" not in model:
        model = f"typesafe-ai/{model}"
    return model


def evaluate_questions(questions: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, question in questions.items():
        if hasattr(question, "model_dump"):
            raw = question.model_dump(exclude_none=True)
        elif isinstance(question, dict):
            raw = {k: v for k, v in question.items() if v is not None}
        else:
            raw = {
                "type": getattr(question, "type", None),
                "instructions": getattr(question, "instructions", None),
                "criteria": getattr(question, "criteria", None),
            }
            raw = {k: v for k, v in raw.items() if v is not None}
        if raw.get("type") == "noul":
            raw["type"] = "boolean"
        out[name] = raw
    return out


def response_from_evaluate(payload: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    nouls: dict[str, Any] = {}
    choices: dict[str, Any] = {}
    for name, answer in (payload.get("answers") or {}).items():
        kind = (answer or {}).get("type")
        if kind == "boolean":
            nouls[name] = SimpleNamespace(noul=float(answer.get("probability") or 0))
        elif kind == "choice":
            choices[name] = SimpleNamespace(
                choice=answer.get("choice"),
                probabilities=answer.get("probabilities"),
            )
    usage_raw = payload.get("usage") or {}
    usage = SimpleNamespace(
        input_tokens=usage_raw.get("input_tokens", usage_raw.get("inputTokens")),
        output_tokens=usage_raw.get("output_tokens", usage_raw.get("outputTokens")),
    )
    return SimpleNamespace(
        nouls=nouls,
        choices=choices,
        scores={},
        model=payload.get("model"),
        usage=usage,
    )


def gateway_post(url: str, *, json: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    import httpx2

    response = httpx2.post(url, json=json, headers=headers, timeout=60.0)
    if response.status_code >= 400:
        snippet = (response.text or "").strip()[:300]
        raise RuntimeError(f"POST {url}: {response.status_code} {snippet}")
    return response.json()


def call_evaluate(state: Any, questions: dict[str, Any]) -> Any:
    kw = client_kwargs()
    url = kw["base_url"] + GATEWAY_EVALUATE_PATH
    payload = gateway_post(
        url,
        json={
            "model": gateway_model(),
            "state": state,
            "questions": evaluate_questions(questions),
        },
        headers={
            "Authorization": f"Bearer {kw['api_key']}",
            "Content-Type": "application/json",
        },
    )
    return response_from_evaluate(payload)


def available() -> bool:
    if not get_settings().jev_triage_enabled:
        return False
    return bool(_api_key())


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
            if uses_gateway():
                response = call_evaluate(state, questions)
            else:
                from typesafe_sdk import TypeSafeClient

                with TypeSafeClient(**client_kwargs()) as client:
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
