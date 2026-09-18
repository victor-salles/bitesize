"""Human corrections for Jev scores. Gold file for later question/threshold work."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import BASE_DIR
from tags import TEMAS, TIPOS

LABELS_PATH = BASE_DIR / "data" / "jev_labels.json"

NOUL_KEYS = ("ad", "clickbait", "press_release", "paywall_teaser")


def item_key(item: dict[str, Any]) -> str:
    url = (item.get("url") or item.get("link") or "").strip()
    if url:
        return url
    title = (item.get("title") or "").strip()
    source = (item.get("source") or "").strip()
    return f"{title}|{source}"


def _load() -> dict[str, Any]:
    if not LABELS_PATH.is_file():
        return {"labels": {}}
    try:
        data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"labels": {}}
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        return {"labels": {}}
    return data


def _write(data: dict[str, Any]) -> None:
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _clean_patch(patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in NOUL_KEYS:
        if key not in patch:
            continue
        try:
            n = float(patch[key])
        except (TypeError, ValueError):
            continue
        out[key] = max(0.0, min(1.0, n))
    if "relevance" in patch:
        try:
            out["relevance"] = max(0, min(100, int(round(float(patch["relevance"])))))
        except (TypeError, ValueError):
            pass
    if "tipo" in patch and patch["tipo"] in TIPOS:
        out["tipo"] = patch["tipo"]
    if "temas" in patch and isinstance(patch["temas"], list):
        out["temas"] = sorted({t for t in patch["temas"] if t in TEMAS})
    return out


def save_label(run_id: str, item: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    cleaned = _clean_patch(patch)
    if not cleaned:
        existing = label_for(run_id, item) or {}
        return existing
    data = _load()
    by_run = data["labels"].setdefault(run_id, {})
    key = item_key(item)
    row = dict(by_run.get(key) or {})
    row.update(cleaned)
    row["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    by_run[key] = row
    _write(data)
    return row


def label_for(run_id: str, item: dict[str, Any]) -> dict[str, Any] | None:
    row = _load()["labels"].get(run_id, {}).get(item_key(item))
    if not row:
        return None
    return {k: v for k, v in row.items() if k != "updated_at"}


def attach_labels(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return payload
    run_id = payload.get("id") or ""
    out = dict(payload)
    items = []
    for item in payload.get("items") or []:
        row = dict(item)
        human = label_for(run_id, item)
        if human:
            row["human"] = human
        items.append(row)
    out["items"] = items
    return out


def export_rows() -> list[dict[str, Any]]:
    import jev_log

    data = _load()
    rows: list[dict[str, Any]] = []
    for run_id, by_key in data["labels"].items():
        run = jev_log.load_run(run_id) or {}
        items = {item_key(it): it for it in run.get("items") or []}
        for key, human in by_key.items():
            item = items.get(key) or {}
            answers = (item.get("jev") or {}).get("answers") or {}
            label = {k: v for k, v in human.items() if k != "updated_at"}
            rows.append(
                {
                    "run_id": run_id,
                    "url": item.get("url") or key,
                    "title": item.get("title") or "",
                    "source": item.get("source") or "",
                    "predicted": {
                        "ad": answers.get("ad"),
                        "clickbait": answers.get("clickbait"),
                        "press_release": answers.get("press_release"),
                        "paywall_teaser": answers.get("paywall_teaser"),
                        "relevance": item.get("relevance"),
                        "tipo": item.get("tipo"),
                        "temas": item.get("temas") or [],
                    },
                    "label": label,
                    "updated_at": human.get("updated_at"),
                }
            )
    return rows
