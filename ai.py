"""
AI transport router.

Reads ai_backend from settings and delegates call() / available()
to the appropriate backend. Callers only import from here.

use_ai_client() swaps in an explicit client for the current context, so a
caller can build an edition with its own AI transport.
"""

import contextvars
from contextlib import contextmanager
from typing import Iterator, Optional, Protocol

from config import get_settings


class AIClient(Protocol):
    def call(self, instruction: str, stdin_data: str, label: str = "") -> Optional[str]: ...

    def available(self) -> bool: ...


_client_override: contextvars.ContextVar[Optional[AIClient]] = contextvars.ContextVar(
    "bitesize_ai_client", default=None
)


@contextmanager
def use_ai_client(client: Optional[AIClient]) -> Iterator[None]:
    """Route call()/available() to *client* inside this block. None keeps the settings backend."""
    token = _client_override.set(client)
    try:
        yield
    finally:
        _client_override.reset(token)


def available() -> bool:
    client = _client_override.get()
    if client is not None:
        return client.available()
    backend = get_settings().ai_backend
    if backend == "ollama":
        from ollama_backend import available as _available
    elif backend == "antigravity":
        from antigravity_backend import available as _available
    else:
        from gemini_backend import available as _available
    return _available()


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    client = _client_override.get()
    if client is not None:
        return client.call(instruction, stdin_data, label)
    backend = get_settings().ai_backend
    if backend == "ollama":
        from ollama_backend import call as _call
    elif backend == "antigravity":
        from antigravity_backend import call as _call
    else:
        from gemini_backend import call as _call
    return _call(instruction, stdin_data, label)


__all__ = ["AIClient", "call", "available", "use_ai_client"]
