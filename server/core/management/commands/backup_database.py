from django.core.management.base import BaseCommand

from core.backup import backup_database


class Command(BaseCommand):
    help = "Copy the SQLite database into BACKUP_DIR and keep the newest BACKUP_KEEP copies."

    def handle(self, **options):
        path = backup_database()
        self.stdout.write(f"Backed up the database to {path}.")
