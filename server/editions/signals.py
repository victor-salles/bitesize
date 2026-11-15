"""Signals other apps hook into."""

from django.dispatch import Signal

# Sent with `edition=` after an edition's EPUB is built and the edition is marked
# succeeded. Delivery (#66) connects here. Receivers run in the worker; their
# errors are logged and never fail the edition.
edition_built = Signal()
