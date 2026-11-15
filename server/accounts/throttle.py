"""Lock out brute-force PIN guessing, per account and per client IP.

Failure counts live in Django's default cache. Each failure re-arms the
timeout, so a lock lifts `LOGIN_LOCKOUT_SECONDS` after the last failed try.
Attempts made while locked are refused before the PIN is checked and are not
counted, so they neither extend the lock nor reveal whether the PIN was right.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    """The client address as seen by the nearest proxy.

    Dokku's nginx sits in front of gunicorn, so REMOTE_ADDR is the proxy. The
    rightmost X-Forwarded-For entry is the one nginx wrote; entries to its
    left come from the client and can be forged.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f"login-failures:{kind}:{digest}"


def _keys(name: str, ip: str) -> list[tuple[str, int]]:
    return [
        (_key("account", name.casefold()), settings.LOGIN_FAILURES_PER_ACCOUNT),
        (_key("ip", ip), settings.LOGIN_FAILURES_PER_IP),
    ]


def is_locked(name: str, ip: str) -> bool:
    return any(cache.get(key, 0) >= limit for key, limit in _keys(name, ip))


def record_failure(name: str, ip: str) -> None:
    for key, _limit in _keys(name, ip):
        cache.set(key, cache.get(key, 0) + 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)


def clear_account(name: str) -> None:
    cache.delete(_key("account", name.casefold()))
