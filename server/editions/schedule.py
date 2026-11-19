"""Daily schedule: queue each reader's edition once their delivery time has come.

`manage.py enqueue_due_editions` runs this from Dokku cron every few minutes.
A reader is due when, in their own time zone, today's delivery time has passed
and they have no edition for today yet. An existing edition, even a failed one,
means the day is handled: failed editions are retried from the admin, not here.
"""

import logging
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Edition, Source

from .services import enqueue_edition

logger = logging.getLogger(__name__)


def enqueue_due_editions(now=None) -> list[Edition]:
    """Queue today's edition for every active reader who is due. Returns the editions queued."""
    now = now or timezone.now()
    enqueued = []
    for user in get_user_model().objects.filter(is_active=True, profile__isnull=False).select_related("profile"):
        profile = user.profile
        local_now = timezone.localtime(now, ZoneInfo(profile.timezone))
        local_date = local_now.date()
        if local_now.time() < profile.delivery_time:
            continue
        if Edition.objects.filter(user=user, edition_date=local_date).exists():
            continue
        reason = _not_ready_reason(user)
        if reason:
            logger.info("Not scheduling %s's edition for %s: %s", user, local_date, reason)
            continue
        enqueued.append(enqueue_edition(user, local_date))
    return enqueued


def _not_ready_reason(user) -> str:
    if not user.profile.kindle_email:
        return "no Kindle address"
    if not Source.objects.active().filter(user=user).exists():
        return "no active sources"
    return ""
