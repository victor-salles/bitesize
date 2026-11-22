"""Consistent copies of the SQLite database, newest `BACKUP_KEEP` kept."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

PREFIX = "server-"
SUFFIX = ".sqlite3"


def backup_database(now: datetime | None = None) -> Path:
    """Copy the live database with SQLite's backup API, which is safe while the web
    and worker processes write (a plain file copy can catch a half-written page or
    miss what is still in the WAL), then drop the oldest copies."""
    stamp = (now or timezone.now()).astimezone(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"{PREFIX}{stamp}{SUFFIX}"
    partial = path.with_name(path.name + ".partial")

    connection.ensure_connection()
    target = sqlite3.connect(partial)
    try:
        connection.connection.backup(target)
    finally:
        target.close()
    # The rename is atomic, so a crash never leaves a truncated file that looks
    # like a backup and would push a good one out of the kept set.
    partial.replace(path)

    _prune(backup_dir, keep=settings.BACKUP_KEEP)
    return path


def _prune(backup_dir: Path, keep: int) -> None:
    # The UTC timestamp in the name sorts in time order.
    backups = sorted(backup_dir.glob(f"{PREFIX}*{SUFFIX}"))
    for old in backups[: max(len(backups) - keep, 0)]:
        old.unlink()
