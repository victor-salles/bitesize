"""Django settings for the BiteSIze server.

Every deploy-specific value comes from an environment variable; see server/README.md.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent

# The digest pipeline (pipeline.py and friends) lives at the repo root, one level
# above server/. `manage.py` and gunicorn only put server/ on the path.
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

DEBUG = env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DJANGO_DEBUG is off")
    SECRET_KEY = "django-insecure-local-development-only"

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_tasks_db",
    "core",
    "accounts",
    "sources",
    "editions",
    "articles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bitesize_server.urls"

# The admin lives at a path from the environment so it is not where scanners
# look first. Unset keeps `admin/`.
_admin_path = os.environ.get("DJANGO_ADMIN_PATH", "admin").strip().strip("/")
if not _admin_path:
    raise ImproperlyConfigured(f"DJANGO_ADMIN_PATH must name a path, got {os.environ['DJANGO_ADMIN_PATH']!r}")
ADMIN_URL = f"{_admin_path}/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bitesize_server.wsgi.application"

# One SQLite file shared by gunicorn and the task worker. WAL plus a busy
# timeout and IMMEDIATE transactions keep the two processes from failing with
# "database is locked" under light concurrent writes.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH") or BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 5,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

# Login lockout counters (accounts.throttle) must be shared by every gunicorn
# worker, so the cache lives in the SQLite database rather than in process
# memory: no extra service on the 1 GB droplet, and counts survive restarts.
# accounts/migrations/0001 creates the table, so `migrate` is enough.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Background work runs through Django's tasks framework, stored in the database
# and executed by `manage.py db_worker` (the Procfile `worker` process).
TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "QUEUES": ["default"],
    }
}

# Built EPUBs go to EDITIONS_DIR/<user id>/<date>/.
EDITIONS_DIR = Path(os.environ.get("DJANGO_EDITIONS_DIR") or BASE_DIR / "media" / "editions")
# A running edition older than this lost its worker; the next task marks it failed.
EDITION_STALE_AFTER = timedelta(hours=2)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Kindle login: name + PIN, then stay signed in. Typing on the Kindle is slow.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_DAYS", default=365) * 24 * 60 * 60

# Failed PIN attempts allowed before a lock, and how long the lock lasts after
# the last failure. A 4-digit PIN has 10,000 values; 5 tries per 15 minutes
# per account keeps a full search over a year away.
LOGIN_FAILURES_PER_ACCOUNT = env_int("DJANGO_LOGIN_FAILURES_PER_ACCOUNT", default=5)
LOGIN_FAILURES_PER_IP = env_int("DJANGO_LOGIN_FAILURES_PER_IP", default=20)
LOGIN_LOCKOUT_SECONDS = env_int("DJANGO_LOGIN_LOCKOUT_MINUTES", default=15) * 60

# Sign-up needs a single-use invite link from staff (accounts.Invite).
INVITE_DAYS = env_int("DJANGO_INVITE_DAYS", default=14)

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Dokku's nginx terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Production is HTTPS only. /healthz stays reachable over plain HTTP for
# container health checks, which call the app directly, not through nginx.
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
# Start HSTS short (1 day) and raise DJANGO_HSTS_SECONDS once HTTPS has held up.
# Subdomains of the app's own host are covered; preload is a one-way door, so off.
SECURE_HSTS_SECONDS = 0 if DEBUG else env_int("DJANGO_HSTS_SECONDS", default=24 * 60 * 60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
# Django's defaults, set here so the security posture is visible in one place.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Everything, including django.request 500s with tracebacks, goes to stdout,
# where `dokku logs` reads it: JSON lines in production, plain text in debug.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "bitesize_server.log_format.JsonFormatter"},
        "text": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "text" if DEBUG else "json",
        }
    },
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

# Who gets error emails (Django's mail_admins handler). Nothing is sent until
# ADMINS is set and an email backend is configured.
ADMINS = env_list("DJANGO_ADMINS")
SERVER_EMAIL = os.environ.get("DJANGO_SERVER_EMAIL") or "root@localhost"

# Server AI: Gemini API with the server's key (see server/README.md).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"
GEMINI_DAILY_REQUEST_CAP = env_int("GEMINI_DAILY_REQUEST_CAP", default=200)
