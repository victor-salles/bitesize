from django.db import transaction

from core.models import Source

from . import catalogue


@transaction.atomic
def add_starter_sources(user, categories=None) -> int:
    """Give `user` the catalogue's sources (optionally only some categories). Skip URLs they already have."""
    have = set(Source.objects.filter(user=user).values_list("url", flat=True))
    new = []
    for category, feeds in catalogue.load().items():
        if categories is not None and category not in categories:
            continue
        for name, url in feeds.items():
            if url not in have:
                have.add(url)
                new.append(Source(user=user, name=name, url=url, category=category))
    Source.objects.bulk_create(new)
    return len(new)
