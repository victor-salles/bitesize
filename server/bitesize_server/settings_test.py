"""Settings for pytest: the real settings plus a throwaway secret key."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-real-key")

from .settings import *  # noqa: E402,F403

# PINs are hashed with PBKDF2 in production; tests only need a hash, fast.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Tests never reach Gemini with a real key from the developer's shell.
GEMINI_API_KEY = ""
# The test client speaks plain HTTP; tests that need the HTTPS redirect turn it on.
SECURE_SSL_REDIRECT = False
