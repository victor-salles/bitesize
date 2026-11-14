"""Settings for pytest: the real settings plus a throwaway secret key."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-real-key")

from .settings import *  # noqa: E402,F403
