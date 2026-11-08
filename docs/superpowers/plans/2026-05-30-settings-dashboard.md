# Settings Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal local HTML dashboard backed by SQLite so every BiteSIze setting (RSS sources, Kindle SMTP, AI, EPUB, integrations, CLI defaults) is editable in the browser and read by the CLI at runtime.

**Architecture:** Single SQLite file (`data/bitesize.db`) holds scalar settings (key/value/type) and normalized RSS sources (categories + feeds). A thin `settings_store.py` module is the only data layer. `config.py` loads a `Settings` snapshot from SQLite on startup (with one-time migration from `sources.json` + `.env`). A Flask app (`dashboard.py`) serves one static HTML page and a small JSON REST API. The CLI pipeline (`main.py`, `kindle.py`, `feed.py`, etc.) reads from the snapshot instead of env/constants/files.

**Tech Stack:** Python 3.13, SQLite (stdlib), Flask, pytest, vanilla HTML/CSS/JS (no frontend build step).

**Out of scope (backlog — do not implement in this plan):**
- Preview digest content before sending
- Preview AI summaries in dashboard
- Magazine-style Kindle cover generation UI

---

## File map

| File | Responsibility |
|------|----------------|
| `settings_store.py` | Schema, CRUD, migration, `Settings` dataclass, `load_settings()` |
| `dashboard.py` | Flask server: static page + `/api/*` routes |
| `dashboard_static/index.html` | Single-page UI (tabs: Settings, Sources, Kindle) |
| `dashboard_static/app.js` | Fetch/save settings and sources |
| `dashboard_static/style.css` | Minimal modern styling |
| `config.py` | Re-exports `load_settings()`, paths; removes hardcoded runtime constants |
| `main.py` | Load settings; build source tree from DB; respect `kindle_delivery_enabled` |
| `kindle.py` | Read SMTP fields from `Settings` argument, not `os.getenv` |
| `feed.py`, `gemini.py`, `epub.py`, `ai.py`, backends | Accept settings via module-level reload or function args (minimal: `config.get_settings()`) |
| `tests/test_settings_store.py` | TDD for store |
| `tests/test_dashboard_api.py` | TDD for HTTP API |
| `requirements.txt` | Add `flask`, `pytest` |
| `.gitignore` | Add `data/` |

---

## Settings schema (SQLite)

### Table `settings`
| key | type | group | default |
|-----|------|-------|---------|
| `ai_backend` | str | ai | `gemini` |
| `ollama_host` | str | ai | `localhost:11434` |
| `ollama_model` | str | ai | `llama3:8b` |
| `ollama_timeout` | int | ai | `120` |
| `gemini_batch_size` | int | ai | `20` |
| `gemini_timeout` | int | ai | `120` |
| `gemini_check_timeout` | int | ai | `6` |
| `max_articles_per_feed` | int | feed | `10` |
| `feed_timeout` | int | feed | `15` |
| `truncate_chars` | int | feed | `450` |
| `user_agent` | str | feed | `BiteSIze/1.0 (+https://github.com/local/bitesize)` |
| `min_body_chars` | int | filter | `180` |
| `min_summary_chars` | int | filter | `80` |
| `index_entries_per_page` | int | epub | `10` |
| `top_picks_on_cover` | int | epub | `6` |
| `kindle_email` | str | kindle | `` |
| `smtp_user` | str | kindle | `` |
| `smtp_password` | str | kindle | `` |
| `smtp_host` | str | kindle | `smtp.gmail.com` |
| `smtp_port` | int | kindle | `587` |
| `kindle_delivery_enabled` | bool | kindle | `true` |
| `integration_gmail` | bool | integrations | `false` |
| `integration_google_calendar` | bool | integrations | `false` |
| `gmail_max_threads` | int | integrations | `30` |
| `gmail_lookback_hours` | int | integrations | `24` |
| `calendar_lookahead_days` | int | integrations | `7` |
| `calendar_lookback_days` | int | integrations | `3` |
| `cli_select_all_sources` | bool | cli | `false` |

### Table `categories`
`id INTEGER PK`, `name TEXT UNIQUE`, `sort_order INTEGER`

### Table `feeds`
`id INTEGER PK`, `category_id INTEGER FK`, `name TEXT`, `url TEXT`, `enabled INTEGER DEFAULT 1`

Unique constraint: `(category_id, name)`.

---

## Dashboard API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/settings` | All settings grouped by `group` |
| PUT | `/api/settings` | Bulk update `{key: value}` |
| GET | `/api/sources` | `{categories: [{id, name, feeds: [{id, name, url, enabled}]}]}` |
| POST | `/api/categories` | `{name}` |
| PUT | `/api/categories/<id>` | `{name}` |
| DELETE | `/api/categories/<id>` | |
| POST | `/api/feeds` | `{category_id, name, url, enabled?}` |
| PUT | `/api/feeds/<id>` | `{name?, url?, enabled?}` |
| DELETE | `/api/feeds/<id>` | |
| POST | `/api/kindle/test` | Send test email using current SMTP settings |
| GET | `/api/health` | `{ok: true}` |

Run dashboard: `python dashboard.py` → `http://127.0.0.1:8765`

---

### Task 1: Settings store foundation

**Files:**
- Create: `settings_store.py`
- Create: `tests/test_settings_store.py`
- Modify: `.gitignore` (add `data/`)
- Modify: `requirements.txt` (add `pytest`)

- [ ] **Step 1: Write failing test for DB init and defaults**

```python
# tests/test_settings_store.py
import tempfile
from pathlib import Path
import settings_store as store

def test_init_db_seeds_default_settings(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    s = store.load_settings()
    assert s.ai_backend in ("gemini", "ollama")
    assert s.max_articles_per_feed == 10
    assert s.kindle_delivery_enabled is True
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `.venv/bin/pytest tests/test_settings_store.py::test_init_db_seeds_default_settings -v`
Expected: FAIL (`init_db` or `load_settings` missing)

- [ ] **Step 3: Implement minimal `settings_store.py`**

Implement: `DB_PATH`, `SETTINGS_DEFAULTS` dict, `init_db()`, `load_settings()` returning `@dataclass Settings` with all fields, `_get_connection()`, seed defaults on first run.

- [ ] **Step 4: Run test — expect PASS**

Run: `.venv/bin/pytest tests/test_settings_store.py::test_init_db_seeds_default_settings -v`

- [ ] **Step 5: Commit**

```bash
git add settings_store.py tests/test_settings_store.py requirements.txt .gitignore
git commit -m "feat: add SQLite settings store with defaults"
```

---

### Task 2: Settings get/set and migration

**Files:**
- Modify: `settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Write failing tests**

```python
def test_set_and_get_setting(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    store.set_setting("ai_backend", "ollama")
    assert store.load_settings().ai_backend == "ollama"

def test_migrate_from_sources_json_and_env(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    sources = tmp_path / "sources.json"
    env = tmp_path / ".env"
    sources.write_text('{"categories":{"Tech":{"HN":"https://hnrss.org/frontpage"}},"integrations":{"gmail":true,"google_calendar":false}}')
    env.write_text("KINDLE_EMAIL=a@kindle.com\nSMTP_USER=u@gmail.com\nAI_BACKEND=ollama\n")
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", sources)
    monkeypatch.setattr(store, "ENV_FILE", env)
    store.init_db()
    store.migrate_from_files_if_empty()
    s = store.load_settings()
    assert s.kindle_email == "a@kindle.com"
    assert s.ai_backend == "ollama"
    assert s.integration_gmail is True
    tree = store.load_sources_tree()
    assert "Tech" in tree
    assert tree["Tech"]["HN"] == "https://hnrss.org/frontpage"
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement `set_setting`, `migrate_from_files_if_empty`, `load_sources_tree`, categories/feeds CRUD helpers**

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_settings_store.py -v`

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: settings migration from sources.json and .env"
```

---

### Task 3: Sources CRUD in store

**Files:**
- Modify: `settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Write failing tests for add/update/delete category and feed**

```python
def test_sources_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()
    cat_id = store.add_category("Brazil")
    feed_id = store.add_feed(cat_id, "G1", "https://g1.globo.com/rss")
    store.update_feed(feed_id, enabled=False)
    tree = store.load_sources_tree(enabled_only=False)
    assert tree["Brazil"]["G1"] == "https://g1.globo.com/rss"
    store.delete_feed(feed_id)
    assert "G1" not in store.load_sources_tree().get("Brazil", {})
```

- [ ] **Step 2–4: Implement CRUD, run tests**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: SQLite CRUD for RSS categories and feeds"
```

---

### Task 4: Wire CLI to settings store

**Files:**
- Modify: `config.py`
- Modify: `main.py`
- Modify: `kindle.py`
- Modify: `ai.py`
- Create: `tests/test_cli_settings.py`

- [ ] **Step 1: Write failing test that main uses DB sources when `--all` equivalent enabled**

```python
def test_build_selected_sources_from_db(tmp_path, monkeypatch):
    # seed DB with one category/feed, cli_select_all_sources=True
    # call helper extracted from main: build_selected_sources(settings, args)
    # assert selected dict matches DB
```

- [ ] **Step 2: Refactor `config.py`**

Replace module-level constants with:
```python
_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        settings_store.init_db()
        settings_store.migrate_from_files_if_empty()
        _settings = settings_store.load_settings()
    return _settings

def reload_settings() -> Settings:
    global _settings
    _settings = None
    return get_settings()
```

Update `feed.py`, `gemini.py`, `epub.py`, backends to call `config.get_settings()` instead of importing constants.

- [ ] **Step 3: Update `main.py`**

- Call `config.get_settings()` after optional `load_env()` (env still allowed as fallback during migration only — prefer DB)
- Load sources via `settings_store.load_sources_tree(enabled_only=True)` instead of `sources.json`
- `--all` flag OR `settings.cli_select_all_sources` selects all enabled feeds
- Skip Kindle when `--no-kindle` OR `not settings.kindle_delivery_enabled`

- [ ] **Step 4: Update `kindle.py`**

```python
def send_to_kindle(epub_path: Path, settings: Settings) -> bool:
    kindle_email = settings.kindle_email.strip()
    ...
```

- [ ] **Step 5: Run tests + manual smoke**

Run: `.venv/bin/pytest tests/ -v`
Run: `.venv/bin/python main.py --all --no-kindle` (should still produce EPUB)

- [ ] **Step 6: Commit**

```bash
git commit -am "feat: CLI reads all runtime config from SQLite settings"
```

---

### Task 5: Flask dashboard API

**Files:**
- Create: `dashboard.py`
- Create: `tests/test_dashboard_api.py`
- Modify: `requirements.txt` (add `flask`)

- [ ] **Step 1: Write failing API tests**

```python
import dashboard
import settings_store as store

def test_get_settings(client, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "d.db")
    store.init_db()
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "ai" in r.get_json()

def test_put_settings(client, tmp_path, monkeypatch):
    ...
    r = client.put("/api/settings", json={"ai_backend": "ollama"})
    assert store.load_settings().ai_backend == "ollama"
```

Use Flask test client fixture with `dashboard.app.config["TESTING"] = True`.

- [ ] **Step 2–4: Implement routes in `dashboard.py`**

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard_api.py requirements.txt
git commit -m "feat: Flask REST API for settings and sources"
```

---

### Task 6: HTML dashboard UI

**Files:**
- Create: `dashboard_static/index.html`
- Create: `dashboard_static/style.css`
- Create: `dashboard_static/app.js`
- Modify: `dashboard.py` (serve static files at `/`)

- [ ] **Step 1: Build single-page UI with three tabs**

**Settings tab:** grouped form fields (AI, Feed, Filter, EPUB, Integrations, CLI). Save button → `PUT /api/settings`.

**Sources tab:** list categories; add/edit/delete category and feeds inline.

**Kindle tab:** SMTP fields + `kindle_delivery_enabled` toggle + "Send test email" button.

Design: clean sans-serif, light gray background, card layout, ~300 lines total across HTML/CSS/JS.

- [ ] **Step 2: Manual test**

Run: `python dashboard.py`, open `http://127.0.0.1:8765`, change a setting, reload, confirm persistence.

- [ ] **Step 3: Commit**

```bash
git add dashboard_static/ dashboard.py
git commit -m "feat: minimal HTML dashboard for BiteSIze settings"
```

---

### Task 7: Kindle test endpoint + README

**Files:**
- Modify: `dashboard.py` (`POST /api/kindle/test`)
- Modify: `kindle.py` (extract `send_test_email(settings)`)
- Modify: `README.md`

- [ ] **Step 1: Write failing test for test endpoint (mock SMTP)**

- [ ] **Step 2: Implement test send (small plaintext body, no EPUB required)**

- [ ] **Step 3: Document dashboard usage in README**

```markdown
## Settings dashboard
python dashboard.py
# → http://127.0.0.1:8765
Settings are stored in data/bitesize.db. The CLI reads from the same database.
```

- [ ] **Step 4: Full test suite**

Run: `.venv/bin/pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: Kindle SMTP test from dashboard; update README"
```

---

## Self-review

| Requirement | Task |
|-------------|------|
| SQLite hosts all settings | 1–2 |
| CLI follows DB settings | 4 |
| View/change every setting | 1–2, 5–6 |
| Sources management | 3, 5–6 |
| Kindle flow setup + test | 4, 7 |
| Backlog items excluded | noted in header |
| TDD with pytest | every task |
| Minimal code | single store module, one Flask file, vanilla frontend |

No placeholders remain; each task has concrete tests and file paths.

---

## Execution handoff

Plan saved. Execution: **subagent-driven development** with TDD per task.
