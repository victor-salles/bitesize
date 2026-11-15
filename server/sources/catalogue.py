"""The starter catalogue: the repo's `sources.json`, read at runtime."""

import json
from pathlib import Path

from django.conf import settings


def default_path() -> Path:
    # server/ is BASE_DIR; sources.json sits at the repo root next to it.
    return Path(settings.BASE_DIR).parent / "sources.json"


def path() -> Path:
    return Path(getattr(settings, "SOURCES_CATALOGUE_PATH", None) or default_path())


def load() -> dict[str, dict[str, str]]:
    """{category: {name: url}}, in file order."""
    with open(path(), encoding="utf-8") as handle:
        return json.load(handle).get("categories", {})


def lookup(category: str, name: str) -> str | None:
    return load().get(category, {}).get(name)
