from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from sources.starter import add_starter_sources


class Command(BaseCommand):
    help = "Give a user the starter catalogue from sources.json, skipping feeds they already follow."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--category", action="append", dest="categories", help="Only this category (repeatable)."
        )

    def handle(self, username, categories=None, **options):
        User = get_user_model()
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist as exc:
            raise CommandError(f"No user named {username}") from exc
        created = add_starter_sources(user, categories=categories)
        self.stdout.write(f"Added {created} source(s) for {username}.")
