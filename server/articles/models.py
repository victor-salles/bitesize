"""Server AI bookkeeping."""

from django.db import models


class AIUsage(models.Model):
    """Gemini requests made on one day, for the daily request cap."""

    day = models.DateField(unique=True)
    requests = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-day"]
        verbose_name = "AI usage"
        verbose_name_plural = "AI usage"

    def __str__(self) -> str:
        return f"{self.day}: {self.requests} requests"
