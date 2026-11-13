import contextvars
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from rich.console import Console

import settings_store
from settings_store import Settings

BASE_DIR = Path(__file__).parent
SOURCES_FILE = BASE_DIR / "sources.json"
OUTPUT_DIR = BASE_DIR / "output"

console = Console()

_settings: Settings | None = None

# Settings installed by use_settings() win over the database for the current
# context, so a caller (one edition per user) never touches data/bitesize.db.
_settings_override: contextvars.ContextVar[Settings | None] = contextvars.ContextVar(
    "bitesize_settings_override", default=None
)


@contextmanager
def use_settings(settings: Settings) -> Iterator[Settings]:
    """Make get_settings() return *settings* inside this block (context-local)."""
    token = _settings_override.set(settings)
    try:
        yield settings
    finally:
        _settings_override.reset(token)


def submit_in_context(pool, fn, *args, **kwargs):
    """pool.submit that carries the caller's context (and so its settings) into the worker."""
    return pool.submit(contextvars.copy_context().run, fn, *args, **kwargs)


def get_settings() -> Settings:
    override = _settings_override.get()
    if override is not None:
        return override
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


def load_env() -> None:
    """Load .env from the project root without overwriting existing env vars."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
