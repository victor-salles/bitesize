from django.core.management.base import BaseCommand

from editions.schedule import enqueue_due_editions


class Command(BaseCommand):
    help = "Queue today's edition for every reader whose delivery time has come in their time zone."

    def handle(self, **options):
        enqueued = enqueue_due_editions()
        self.stdout.write(f"Enqueued {len(enqueued)} edition(s).")
