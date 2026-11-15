"""Create the cache table that holds login lockout counters (settings.CACHES).

`createcachetable` is idempotent and skips tables that already exist, so
running it from a migration keeps `migrate` the only deploy step.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = []

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
