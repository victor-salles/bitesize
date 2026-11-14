import importlib.util
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "bitesize_server" / "settings.py"
ENV_VARS = [
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_DB_PATH",
]


@pytest.fixture
def load_settings(monkeypatch):
    """Execute settings.py in a fresh module under a controlled environment."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    def load(**env):
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        spec = importlib.util.spec_from_file_location(
            "bitesize_server._settings_under_test", SETTINGS_FILE
        )
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "bitesize_server"
        spec.loader.exec_module(module)
        return module

    return load


def test_production_requires_secret_key(load_settings):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        load_settings()


def test_production_reads_env(load_settings, tmp_path):
    db = tmp_path / "server.sqlite3"
    settings = load_settings(
        DJANGO_SECRET_KEY="s3cr3t",
        DJANGO_ALLOWED_HOSTS="bitesize.example.com, localhost",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://bitesize.example.com",
        DJANGO_DB_PATH=str(db),
    )

    assert settings.DEBUG is False
    assert settings.SECRET_KEY == "s3cr3t"
    assert settings.ALLOWED_HOSTS == ["bitesize.example.com", "localhost"]
    assert settings.CSRF_TRUSTED_ORIGINS == ["https://bitesize.example.com"]
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert settings.DATABASES["default"]["NAME"] == str(db)
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True


def test_production_defaults_to_no_allowed_hosts(load_settings):
    settings = load_settings(DJANGO_SECRET_KEY="s3cr3t")

    assert settings.ALLOWED_HOSTS == []
    assert settings.CSRF_TRUSTED_ORIGINS == []


def test_debug_uses_dev_key_and_local_hosts(load_settings):
    settings = load_settings(DJANGO_DEBUG="true")

    assert settings.DEBUG is True
    assert settings.SECRET_KEY.startswith("django-insecure-")
    assert "localhost" in settings.ALLOWED_HOSTS
    assert settings.SESSION_COOKIE_SECURE is False


def test_default_database_is_sqlite_next_to_manage_py(load_settings):
    settings = load_settings(DJANGO_SECRET_KEY="s3cr3t")

    name = Path(settings.DATABASES["default"]["NAME"])
    assert name.name == "db.sqlite3"
    assert name.parent == SETTINGS_FILE.parents[1]


def test_invalid_debug_value_is_rejected(load_settings):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_DEBUG"):
        load_settings(DJANGO_DEBUG="maybe", DJANGO_SECRET_KEY="s3cr3t")


def test_tasks_use_database_backend(settings):
    assert settings.TASKS["default"]["BACKEND"] == "django_tasks_db.DatabaseBackend"
    assert "django_tasks_db" in settings.INSTALLED_APPS
