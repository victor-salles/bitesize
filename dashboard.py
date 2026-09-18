"""Local settings dashboard — Flask REST API + static HTML UI."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import settings_store as store
from config import BASE_DIR, load_env, reload_settings
import jev_labels
import jev_log
from themes import list_themes, replace_themes
from kindle import send_test_email
from preview import PREVIEW_FETCH_LIMIT, build_source_preview

load_env()

STATIC_DIR = Path(__file__).parent / "dashboard_static"
HOST = "127.0.0.1"
PORT = 8765
TOKEN_FILE = BASE_DIR / "data" / "dashboard.token"


def _resolve_dashboard_token() -> str:
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if token:
        return token
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    print(f"Dashboard write token saved to {TOKEN_FILE}")
    return token


DASHBOARD_TOKEN = _resolve_dashboard_token()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")


def _require_auth():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {DASHBOARD_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401
    return None


@app.before_request
def check_auth():
    if request.method == "OPTIONS" or request.path == "/api/health":
        return None
    if request.path.startswith("/api/") and request.method != "GET":
        return _require_auth()
    return None


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/settings")
def get_settings_api():
    return jsonify(store.settings_for_api())


@app.put("/api/settings")
def put_settings_api():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    try:
        store.update_settings(data)
        reload_settings()
    except KeyError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(store.settings_for_api())


@app.get("/api/sources")
def get_sources_api():
    return jsonify(store.load_sources_for_api())


@app.get("/api/preview")
def get_preview_api():
    max_headlines = request.args.get("max", default=PREVIEW_FETCH_LIMIT, type=int)
    max_headlines = max(1, min(int(max_headlines or PREVIEW_FETCH_LIMIT), PREVIEW_FETCH_LIMIT))
    return jsonify(
        build_source_preview(
            store.load_sources_for_api(),
            max_headlines=max_headlines,
        )
    )


@app.post("/api/categories")
def post_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    cat_id = store.add_category(name)
    return jsonify({"id": cat_id, "name": name}), 201


@app.put("/api/categories/<int:category_id>")
def put_category(category_id: int):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    store.update_category(category_id, name)
    return jsonify({"id": category_id, "name": name})


@app.delete("/api/categories/<int:category_id>")
def delete_category(category_id: int):
    store.delete_category(category_id)
    return jsonify({"ok": True})


@app.post("/api/feeds")
def post_feed():
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id")
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    if not category_id or not name or not url:
        return jsonify({"error": "category_id, name, and url are required"}), 400
    feed_id = store.add_feed(
        int(category_id),
        name,
        url,
        enabled=bool(data.get("enabled", True)),
    )
    return jsonify({"id": feed_id, "name": name, "url": url}), 201


@app.put("/api/feeds/<int:feed_id>")
def put_feed(feed_id: int):
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "name" in data:
        kwargs["name"] = str(data["name"]).strip()
    if "url" in data:
        kwargs["url"] = str(data["url"]).strip()
    if "enabled" in data:
        kwargs["enabled"] = bool(data["enabled"])
    store.update_feed(feed_id, **kwargs)
    return jsonify({"id": feed_id, **kwargs})


@app.delete("/api/feeds/<int:feed_id>")
def delete_feed(feed_id: int):
    store.delete_feed(feed_id)
    return jsonify({"ok": True})


@app.get("/api/jev/themes")
def get_jev_themes():
    return jsonify({"themes": list_themes()})


@app.put("/api/jev/themes")
def put_jev_themes():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Expected JSON array"}), 400
    try:
        themes = replace_themes(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"themes": themes})


@app.get("/api/jev/runs")
def list_jev_runs():
    return jsonify({"runs": jev_log.list_runs()})


@app.get("/api/jev/runs/<run_id>")
def get_jev_run(run_id: str):
    payload = jev_labels.attach_labels(jev_log.load_run(run_id))
    if payload is None:
        return jsonify({"error": "Run not found"}), 404
    payload["themes"] = list_themes()
    return jsonify(payload)


@app.post("/api/jev/labels")
def save_jev_label():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    run_id = str(data.get("run_id") or "")
    payload = jev_log.load_run(run_id)
    if payload is None:
        return jsonify({"error": "Run not found"}), 404
    items = payload.get("items") or []
    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        return jsonify({"error": "index required"}), 400
    if index < 0 or index >= len(items):
        return jsonify({"error": "index out of range"}), 400
    item = items[index]
    patch = {
        k: data[k]
        for k in (
            "keep",
            "ad",
            "clickbait",
            "press_release",
            "paywall_teaser",
            "relevance",
            "tipo",
            "temas",
        )
        if k in data
    }
    human = jev_labels.save_label(run_id, item, patch)
    return jsonify({"ok": True, "human": human, "index": index})


@app.get("/api/jev/labels/export")
def export_jev_labels():
    return jsonify({"rows": jev_labels.export_rows()})


@app.post("/api/kindle/test")
def kindle_test():
    settings = store.load_settings()
    ok, message = send_test_email(settings)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "message": message}), status


def main() -> None:
    store.init_db()
    store.migrate_from_files_if_empty()
    print(f"BiteSIze dashboard → http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
