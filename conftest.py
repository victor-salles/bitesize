import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "allow_jev: exercise Jev triage instead of stubbing it off",
    )


@pytest.fixture(autouse=True)
def jev_triage_off(monkeypatch, request):
    """Keep digest tests on the writing-model path unless they opt into Jev."""
    if request.node.get_closest_marker("allow_jev"):
        return
    monkeypatch.setattr("jev_triage.available", lambda: False)


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    import settings_store as store

    db = tmp_path / "bitesize.db"
    sources = tmp_path / "sources.json"
    env = tmp_path / ".env"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", sources)
    monkeypatch.setattr(store, "ENV_FILE", env)
    return {"db": db, "sources": sources, "env": env}
