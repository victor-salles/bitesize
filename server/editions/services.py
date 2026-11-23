"""The edition queue: put editions on it, and build them one at a time.

One `db_worker` process runs `tasks.build_user_edition` serially, so editions
build in the order they were queued. `claim_edition` also refuses to start one
while another is running, so a second worker started by mistake waits instead
of building two editions at once on the 1 GB droplet.
"""

import logging
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Edition, Source

from .signals import edition_built

logger = logging.getLogger(__name__)

# How long a task waits before checking again when another edition is running.
BUSY_RETRY_DELAY = timedelta(seconds=60)

SKIPPED = "skipped"
DEFERRED = "deferred"


# Run time assumed for an edition when none has been built yet.
DEFAULT_RUN_TIME = timedelta(minutes=10)
# How many recent succeeded builds the typical run time comes from.
RUN_TIME_SAMPLE = 20
# A wait above this many typical builds is "longer than usual".
LONGER_THAN_USUAL = 2


@dataclass(frozen=True)
class QueueStatus:
    """Where a user's edition for today stands in the queue."""

    edition: Edition | None
    # Queued or running editions that will build before it; None unless it is queued or running.
    ahead: int | None
    # Until it is built; None unless it is queued or running.
    estimated_wait: timedelta | None
    typical_run_time: timedelta
    # False when typical_run_time is DEFAULT_RUN_TIME because nothing has been built yet.
    from_history: bool
    longer_than_usual: bool


class EditionError(Exception):
    """An edition that cannot be built, with a message for the user and the admin."""


NO_SOURCES_MESSAGE = "Add at least one active source before requesting an edition."


def has_active_sources(user) -> bool:
    """An edition is built from the reader's active sources, so without one it can only fail."""
    return Source.objects.active().filter(user=user).exists()


def enqueue_edition(user, edition_date: date) -> Edition:
    """Queue `user`'s edition for `edition_date`.

    Creates the edition, or re-queues it if it failed. An edition that is
    already queued, running or built is returned as it is.
    """
    with transaction.atomic():
        edition, created = Edition.objects.get_or_create(user=user, edition_date=edition_date)
        if created:
            _enqueue_task(edition)
        elif edition.status == Edition.Status.FAILED:
            _requeue(edition)
    return edition


def local_today(user) -> date:
    return timezone.localdate(timezone=ZoneInfo(user.profile.timezone))


def queue_status(user) -> QueueStatus:
    """Today's edition for `user`, how many editions build before it and how long until it is built."""
    edition = Edition.objects.filter(user=user, edition_date=local_today(user)).first()
    typical, from_history = typical_run_time()
    ahead = wait = None
    if edition and edition.status in (Edition.Status.QUEUED, Edition.Status.RUNNING):
        before = list(_editions_before(edition))
        ahead = len(before)
        wait = sum((_time_left(other, typical) for other in [*before, edition]), timedelta(0))
    return QueueStatus(
        edition=edition,
        ahead=ahead,
        estimated_wait=wait,
        typical_run_time=typical,
        from_history=from_history,
        longer_than_usual=wait is not None and wait > LONGER_THAN_USUAL * typical,
    )


def typical_run_time() -> tuple[timedelta, bool]:
    """Median run time of recent succeeded editions, and whether there were any."""
    recent = (
        Edition.objects.filter(status=Edition.Status.SUCCEEDED, started_at__isnull=False, finished_at__isnull=False)
        .order_by("-finished_at")
        .only("started_at", "finished_at")[:RUN_TIME_SAMPLE]
    )
    run_times = [edition.run_time for edition in recent]
    if not run_times:
        return DEFAULT_RUN_TIME, False
    return statistics.median(run_times), True


def _editions_before(edition: Edition):
    """Editions the worker builds before `edition`: the running one, then the queue in queued_at order."""
    if edition.status == Edition.Status.RUNNING:
        return Edition.objects.none()
    return Edition.objects.filter(
        Q(status=Edition.Status.RUNNING)
        | Q(status=Edition.Status.QUEUED, queued_at__lt=edition.queued_at)
        | Q(status=Edition.Status.QUEUED, queued_at=edition.queued_at, pk__lt=edition.pk)
    ).only("status", "started_at")


def _time_left(edition: Edition, typical: timedelta) -> timedelta:
    if edition.status == Edition.Status.RUNNING and edition.started_at:
        return max(typical - (timezone.now() - edition.started_at), timedelta(0))
    return typical


def retry_edition(edition: Edition) -> bool:
    """Queue a failed edition again, at the back of the queue. False if it has not failed."""
    with transaction.atomic():
        requeued = _requeue(edition)
    return requeued


def _requeue(edition: Edition) -> bool:
    updated = Edition.objects.filter(pk=edition.pk, status=Edition.Status.FAILED).update(
        status=Edition.Status.QUEUED,
        queued_at=timezone.now(),
        started_at=None,
        finished_at=None,
        error="",
    )
    if not updated:
        return False
    edition.refresh_from_db()
    _enqueue_task(edition)
    return True


def _enqueue_task(edition: Edition, run_after=None) -> None:
    from .tasks import build_user_edition

    task = build_user_edition.using(run_after=run_after) if run_after else build_user_edition
    task.enqueue(edition.pk)


def claim_edition(edition_id: int) -> Edition | str:
    """Mark the edition running and return it, or say why it cannot start.

    Returns SKIPPED when the edition is gone or not queued (already built, or
    claimed by another task), and DEFERRED when another edition is running; the
    task is then queued again for later.
    """
    now = timezone.now()
    with transaction.atomic():
        _fail_stale_runs(now)
        busy = Edition.objects.filter(status=Edition.Status.RUNNING).exclude(pk=edition_id).exists()
        if not busy:
            claimed = Edition.objects.filter(pk=edition_id, status=Edition.Status.QUEUED).update(
                status=Edition.Status.RUNNING, started_at=now, finished_at=None, error=""
            )
            if not claimed:
                return SKIPPED
            return Edition.objects.select_related("user__profile").get(pk=edition_id)
        if not Edition.objects.filter(pk=edition_id, status=Edition.Status.QUEUED).exists():
            return SKIPPED
        _enqueue_task(Edition(pk=edition_id), run_after=now + BUSY_RETRY_DELAY)
        return DEFERRED


def _fail_stale_runs(now) -> None:
    """A running edition older than EDITION_STALE_AFTER lost its worker (crash, deploy)."""
    stale = Edition.objects.filter(
        status=Edition.Status.RUNNING, started_at__lt=now - settings.EDITION_STALE_AFTER
    )
    for edition in stale:
        logger.warning("Edition %s has been running since %s; marking it failed", edition.pk, edition.started_at)
    stale.update(
        status=Edition.Status.FAILED,
        finished_at=now,
        error="Stale: the worker stopped while building this edition. Retry it.",
    )


def build_claimed_edition(edition: Edition) -> str:
    """Build a running edition through the pipeline and record how it went."""
    import pipeline

    try:
        config = edition_config(edition)
        if not config.sources:
            raise EditionError("No active sources to build an edition from.")
        result = pipeline.build_edition(config)
        edition.record_result(result)
        if not result.epub_path:
            raise EditionError("No readable articles were left, so no EPUB was written.")
    except Exception as exc:
        logger.exception("Edition %s failed", edition.pk)
        edition.status = Edition.Status.FAILED
        edition.error = str(exc) if isinstance(exc, EditionError) else f"{type(exc).__name__}: {exc}"
        edition.finished_at = timezone.now()
        edition.save(update_fields=["status", "error", "finished_at"])
        return edition.status

    edition.status = Edition.Status.SUCCEEDED
    edition.finished_at = timezone.now()
    edition.save(update_fields=["status", "finished_at"])

    # Hook point for delivery (#66): the EPUB is at edition.epub_path.
    for receiver, response in edition_built.send_robust(sender=Edition, edition=edition):
        if isinstance(response, Exception):
            logger.error("edition_built receiver %r failed for edition %s", receiver, edition.pk, exc_info=response)
    return edition.status


def edition_config(edition: Edition):
    """The pipeline inputs for `edition`: its user's profile and active sources, the
    server's Gemini client and the article cache shared by every user."""
    from articles.services import get_article_cache, get_server_ai_client
    from pipeline import EditionConfig

    profile = edition.user.profile
    earlier = edition.earlier_built()
    previous = earlier.only("topic_counts").first()
    return EditionConfig(
        sources=Source.objects.edition_sources(edition.user),
        output_dir=edition_dir(edition),
        language=profile.language,
        now=timezone.localtime(timezone.now(), ZoneInfo(profile.timezone)),
        ai=get_server_ai_client(),
        article_cache=get_article_cache(),
        edition_number=earlier.count() + 1,
        # Empty for an edition built before topic counts were stored: no trend beats a wrong one.
        previous_topic_counts=(previous.topic_counts or None) if previous else None,
    )


def edition_dir(edition: Edition) -> Path:
    """`EDITIONS_DIR/<user id>/<date>/`, created if missing."""
    path = Path(settings.EDITIONS_DIR) / str(edition.user_id) / edition.edition_date.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path
