"""Background tasks, run by `manage.py db_worker` (one process; see server/README.md)."""

from django.tasks import task

from . import services


@task
def build_user_edition(edition_id: int) -> str:
    """Build one queued edition. Returns its final status, "skipped" or "deferred"."""
    edition = services.claim_edition(edition_id)
    if isinstance(edition, str):
        return edition
    return services.build_claimed_edition(edition)
