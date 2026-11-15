"""Server AI client: the Gemini API with the server's key and a daily request cap.

Implements `ai.AIClient`. Pass it as `EditionConfig.ai`. Once the day's cap is
spent, available() turns False and call() returns None, so the pipeline builds
the no-summary edition.
"""

import logging
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import AIUsage

logger = logging.getLogger(__name__)

TIMEOUT_MS = 120_000


class GeminiClient:
    def __init__(self, *, api_key: str, model: str, daily_cap: int, sdk: Any = None):
        self._api_key = api_key
        self.model = model
        self.daily_cap = daily_cap
        self._sdk = sdk

    @classmethod
    def from_settings(cls, sdk: Any = None) -> "GeminiClient":
        return cls(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            daily_cap=settings.GEMINI_DAILY_REQUEST_CAP,
            sdk=sdk,
        )

    def __repr__(self) -> str:  # never show the key
        return f"GeminiClient(model={self.model!r}, daily_cap={self.daily_cap})"

    def available(self) -> bool:
        return bool(self._api_key) and self._requests_today() < self.daily_cap

    def call(self, instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
        if not self._api_key:
            return None
        if not self._reserve_request():
            logger.warning("Gemini daily cap of %d requests reached; skipping %s", self.daily_cap, label or "call")
            return None
        from google.genai import types

        try:
            response = self._client().models.generate_content(
                model=self.model,
                contents=stdin_data,
                config=types.GenerateContentConfig(system_instruction=instruction),
            )
        except Exception as exc:
            # Log the type and status only: SDK messages can echo request details.
            logger.warning(
                "Gemini call %s failed: %s %s", label or "", type(exc).__name__, getattr(exc, "code", "")
            )
            return None
        return response.text

    def _client(self):
        if self._sdk is None:
            from google import genai
            from google.genai import types

            self._sdk = genai.Client(api_key=self._api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        return self._sdk

    def _requests_today(self) -> int:
        usage = AIUsage.objects.filter(day=timezone.localdate()).first()
        return usage.requests if usage else 0

    def _reserve_request(self) -> bool:
        """Count one request against today's cap; False when the cap is spent."""
        with transaction.atomic():
            usage, _ = AIUsage.objects.get_or_create(day=timezone.localdate())
            return bool(
                AIUsage.objects.filter(pk=usage.pk, requests__lt=self.daily_cap).update(requests=F("requests") + 1)
            )
