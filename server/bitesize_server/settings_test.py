"""Settings for pytest: the real settings plus a throwaway secret key."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-real-key")

from .settings import *  # noqa: E402,F403

# Tests never reach Gemini with a real key from the developer's shell.
GEMINI_API_KEY = ""
