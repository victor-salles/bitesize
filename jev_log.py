"""Persist each Jev classify run as JSON under output/jev/."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import OUTPUT_DIR

JEV_DIR = OUTPUT_DIR / "jev"
_RUN_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,80}$")


def _safe_run_id(run_id: str) -> str | None:
    if not run_id or not _RUN_ID_RE.match(run_id):
        return None
    if ".." in run_id:
        return None
    return run_id


def item_record(art: dict) -> dict[str, Any]:
    jev = art.get("jev") or {}
    return {
        "title": art.get("title") or "",
        "source": art.get("source") or "",
        "category": art.get("category") or "",
        "url": art.get("link") or art.get("url") or "",
        "skip": bool(art.get("skip")),
        "skip_reason": art.get("skip_reason"),
        "relevance": art.get("relevance"),
        "tipo": art.get("tipo"),
        "temas": list(art.get("temas") or []),
        "jev": jev,
        "error": art.get("jev_error"),
    }


def _counts(items: list[dict[str, Any]]) -> dict[str, int]:
    skipped = sum(1 for it in items if it.get("skip"))
    errors = sum(1 for it in items if it.get("error"))
    return {
        "article_count": len(items),
        "skipped": skipped,
        "errors": errors,
        "kept": len(items) - skipped,
    }


def _unique_path(stem: str) -> Path:
    JEV_DIR.mkdir(parents=True, exist_ok=True)
    path = JEV_DIR / f"{stem}.json"
    n = 2
    while path.exists():
        path = JEV_DIR / f"{stem}-{n}.json"
        n += 1
    return path


def write_run(
    articles: list[dict],
    *,
    min_keep: int = 0,
    workers: int = 4,
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    stem = now.strftime("%Y-%m-%dT%H%M%S")
    path = _unique_path(stem)
    items = [item_record(art) for art in articles]
    payload: dict[str, Any] = {
        "id": path.stem,
        "started_at": now.isoformat(timespec="seconds"),
        "min_keep": int(min_keep),
        "workers": int(workers),
        "path": str(path),
        **_counts(items),
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload.get("id"),
        "started_at": payload.get("started_at"),
        "path": payload.get("path"),
        "article_count": payload.get("article_count", 0),
        "kept": payload.get("kept", 0),
        "skipped": payload.get("skipped", 0),
        "errors": payload.get("errors", 0),
        "min_keep": payload.get("min_keep", 0),
    }


def list_runs() -> list[dict[str, Any]]:
    if not JEV_DIR.is_dir():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(JEV_DIR.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        payload.setdefault("id", path.stem)
        payload.setdefault("path", str(path))
        runs.append(_summary(payload))
    return runs


def load_run(run_id: str) -> dict[str, Any] | None:
    safe = _safe_run_id(run_id)
    if not safe:
        return None
    path = JEV_DIR / f"{safe}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("id", path.stem)
    payload.setdefault("path", str(path))
    return payload
