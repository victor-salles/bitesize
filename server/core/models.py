"""Core data for the multi-user server: who reads, what they follow, what they got."""

from datetime import time
from functools import cache
from zoneinfo import available_timezones

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# Must match ai_locale.LANGUAGE_LABELS: the value goes to EditionConfig.language.
LANGUAGES = [
    ("pt-BR", "Português (Brasil)"),
    ("en", "English"),
]
DEFAULT_LANGUAGE = "pt-BR"

KINDLE_DOMAINS = {"kindle.com", "free.kindle.com"}


def validate_kindle_email(value: str) -> None:
    domain = value.rpartition("@")[2].lower()
    if domain not in KINDLE_DOMAINS:
        raise ValidationError(
            "Use your Send-to-Kindle address (ending in @kindle.com or @free.kindle.com).",
            code="not_kindle",
        )


@cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def validate_timezone(value: str) -> None:
    if value not in _timezones():
        raise ValidationError("Unknown time zone: %(value)s", code="bad_timezone", params={"value": value})


class Profile(models.Model):
    """Per-user digest settings. Created automatically with each User."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    kindle_email = models.EmailField(blank=True, validators=[validate_kindle_email])
    timezone = models.CharField(max_length=64, default="America/Sao_Paulo", validators=[validate_timezone])
    # Local time, in `timezone`, when the edition should arrive.
    delivery_time = models.TimeField(default=time(7, 0))
    language = models.CharField(max_length=8, choices=LANGUAGES, default=DEFAULT_LANGUAGE)
    # Set once the user has added the server's sender address in Amazon (#60).
    sender_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        Profile.objects.get_or_create(user=instance)


class SourceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active=True)

    def edition_sources(self, user) -> dict[str, dict[str, str]]:
        """The user's active sources shaped as `EditionConfig.sources`: {category: {name: url}}."""
        grouped: dict[str, dict[str, str]] = {}
        for category, name, url in (
            self.active().filter(user=user).order_by("category", "name").values_list("category", "name", "url")
        ):
            grouped.setdefault(category, {})[name] = url
        return grouped


class Source(models.Model):
    """One RSS feed a user follows, filed under a category (an EPUB section)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sources")
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=1000)
    category = models.CharField(max_length=80)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = SourceQuerySet.as_manager()

    class Meta:
        ordering = ["user", "category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "url"], name="source_unique_url_per_user"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"


class Edition(models.Model):
    """One user's digest for one date: its place in the queue, its build and its delivery."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class Delivery(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="editions")
    edition_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    queued_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    epub_path = models.CharField(max_length=500, blank=True)

    delivery_status = models.CharField(max_length=16, choices=Delivery.choices, default=Delivery.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.TextField(blank=True)

    # Copied from pipeline.EditionResult.
    raw_count = models.PositiveIntegerField(default=0)
    full_text_count = models.PositiveIntegerField(default=0)
    kept_count = models.PositiveIntegerField(default=0)
    filtered_count = models.PositiveIntegerField(default=0)
    article_count = models.PositiveIntegerField(default=0)
    section_counts = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-edition_date", "-queued_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "edition_date"], name="edition_one_per_user_per_date"),
        ]
        indexes = [models.Index(fields=["status", "queued_at"], name="edition_queue_idx")]

    def __str__(self) -> str:
        return f"{self.user} {self.edition_date} ({self.status})"

    @property
    def run_time(self):
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def record_result(self, result) -> None:
        """Store a `pipeline.EditionResult`'s EPUB path and counts."""
        self.epub_path = str(result.epub_path) if result.epub_path else ""
        for field in ("raw_count", "full_text_count", "kept_count", "filtered_count", "article_count"):
            setattr(self, field, getattr(result, field, 0))
        self.section_counts = dict(getattr(result, "section_counts", {}))
        self.save()


class Article(models.Model):
    """AI output for one article URL in one language, shared by every user whose edition includes it."""

    url = models.URLField(max_length=1000)
    language = models.CharField(max_length=8, choices=LANGUAGES)
    title = models.CharField(max_length=500, blank=True)
    source = models.CharField(max_length=120, blank=True)
    text_length = models.PositiveIntegerField(default=0)
    # sha256 of the fetched text, to tell when a cached summary is stale.
    text_hash = models.CharField(max_length=64, blank=True)
    summary = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["url", "language"], name="article_unique_url_language"),
        ]

    def __str__(self) -> str:
        return self.title or self.url
