import json
import sqlite3
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from core.backup import backup_database

NOON = datetime(2026, 11, 22, 3, 0, 5, tzinfo=UTC)


@pytest.fixture
def backup_dir(settings, tmp_path):
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.BACKUP_KEEP = 3
    return settings.BACKUP_DIR


def usernames_in(path: Path) -> list[str]:
    with sqlite3.connect(path) as copy:
        return [row[0] for row in copy.execute("SELECT username FROM auth_user ORDER BY username")]


@pytest.mark.django_db(transaction=True)
def test_backup_is_a_readable_copy_named_by_date(backup_dir):
    User.objects.create_user(username="ana", password="1234")

    path = backup_database(now=NOON)

    assert path == backup_dir / "server-2026-11-22T030005Z.sqlite3"
    assert usernames_in(path) == ["ana"]
    assert sorted(p.name for p in backup_dir.iterdir()) == ["server-2026-11-22T030005Z.sqlite3"]


@pytest.mark.django_db(transaction=True)
def test_backup_keeps_only_the_newest_copies(backup_dir):
    backup_dir.mkdir(parents=True)
    for day in ("2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"):
        (backup_dir / f"server-{day}T030000Z.sqlite3").write_bytes(b"old")
    (backup_dir / "notes.txt").write_text("not a backup")

    backup_database(now=NOON)

    assert sorted(p.name for p in backup_dir.iterdir()) == [
        "notes.txt",
        "server-2026-11-20T030000Z.sqlite3",
        "server-2026-11-21T030000Z.sqlite3",
        "server-2026-11-22T030005Z.sqlite3",
    ]


@pytest.mark.django_db(transaction=True)
def test_command_reports_the_backup_path(backup_dir):
    out = StringIO()

    call_command("backup_database", stdout=out)

    [path] = backup_dir.iterdir()
    assert out.getvalue() == f"Backed up the database to {path}.\n"


def test_dokku_cron_backs_up_daily():
    app_json = json.loads((Path(__file__).resolve().parents[2] / "app.json").read_text())

    assert {
        "command": "python server/manage.py backup_database",
        "schedule": "0 3 * * *",
        "concurrency_policy": "forbid",
    } in app_json["cron"]
