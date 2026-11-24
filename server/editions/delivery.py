"""Email built editions to the reader's Kindle through Resend's HTTP API.

Delivery runs as its own task (`tasks.deliver_edition`), queued when an edition
is built, so a slow or failed send never fails the build. The result is
recorded on the edition: delivered, or failed with the reason.
"""

import base64
import logging
from email.utils import parseaddr
from pathlib import Path

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Edition

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT = 60
# Resend takes 40 MB per email, attachments counted after base64 encoding. That
# is below Kindle's 50 MB per document, so it is the only limit to check.
MAX_EMAIL_BYTES = 40 * 1024 * 1024

SKIPPED = "skipped"


class DeliveryError(Exception):
    """A delivery that cannot be made, with a message for the reader and the admin."""


def max_epub_bytes() -> int:
    """Largest EPUB whose base64 encoding fits in MAX_EMAIL_BYTES."""
    return MAX_EMAIL_BYTES // 4 * 3


def sender_address() -> str:
    """The bare address readers approve in Amazon, from DELIVERY_FROM_EMAIL."""
    return parseaddr(settings.DELIVERY_FROM_EMAIL)[1]


def deliver(edition_id: int) -> str:
    """Send a built edition waiting for delivery and record how it went.

    Returns the new delivery status, or SKIPPED when the edition is gone, not
    built, or not pending (already delivered, or failed and not retried).
    """
    edition = (
        Edition.objects.select_related("user__profile")
        .filter(pk=edition_id, status=Edition.Status.SUCCEEDED, delivery_status=Edition.Delivery.PENDING)
        .first()
    )
    if edition is None:
        return SKIPPED
    try:
        send_epub(edition)
    except Exception as exc:
        logger.exception("Delivery of edition %s failed", edition.pk)
        edition.delivery_status = Edition.Delivery.FAILED
        edition.delivery_error = str(exc) if isinstance(exc, DeliveryError) else f"{type(exc).__name__}: {exc}"
        edition.save(update_fields=["delivery_status", "delivery_error"])
        return edition.delivery_status

    edition.delivery_status = Edition.Delivery.DELIVERED
    edition.delivered_at = timezone.now()
    edition.delivery_error = ""
    edition.save(update_fields=["delivery_status", "delivered_at", "delivery_error"])
    return edition.delivery_status


def send_epub(edition: Edition) -> None:
    """Email the edition's EPUB to its reader's Kindle. Raises DeliveryError."""
    api_key = settings.RESEND_API_KEY
    if not api_key:
        raise DeliveryError("RESEND_API_KEY is not set, so the server cannot send email.")
    kindle_email = edition.user.profile.kindle_email
    if not kindle_email:
        raise DeliveryError("No Kindle address: add one on the Delivery tab.")
    epub = _read_epub(edition.epub_path)

    day = edition.edition_date.isoformat()
    title = kindle_title(edition)
    try:
        response = requests.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": settings.DELIVERY_FROM_EMAIL,
                "to": [kindle_email],
                "subject": title,
                "text": f"Your BiteSIze edition for {day} is attached.",
                "attachments": [
                    {"filename": f"{title}.epub", "content": base64.b64encode(epub).decode("ascii")}
                ],
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise DeliveryError(f"Could not reach Resend: {type(exc).__name__}: {exc}") from exc
    if not response.ok:
        raise DeliveryError(f"Resend answered {response.status_code}: {_error_message(response)}")


def kindle_title(edition) -> str:
    """The name the Kindle library shows: Send to Kindle titles an emailed EPUB after its file name."""
    from ai_locale import EPUB_LABELS

    language = edition.user.profile.language
    month = EPUB_LABELS.get(language, EPUB_LABELS["en"])["months"][edition.edition_date.month - 1]
    day, year = edition.edition_date.day, edition.edition_date.year
    date = f"{day} de {month} de {year}" if language == "pt-BR" else f"{day} {month} {year}"
    return f"BiteSIze – {date}"


def _read_epub(epub_path: str) -> bytes:
    path = Path(epub_path) if epub_path else None
    if path is None or not path.is_file():
        raise DeliveryError(f"EPUB not found at {epub_path or '(no path)'}.")
    size, limit = path.stat().st_size, max_epub_bytes()
    if size > limit:
        raise DeliveryError(
            f"The EPUB is too large to email: {size} bytes, over the {limit}-byte limit "
            f"(Resend takes {MAX_EMAIL_BYTES} bytes per email after base64 encoding)."
        )
    return path.read_bytes()


def _error_message(response) -> str:
    try:
        message = response.json().get("message")
    except ValueError:
        message = None
    return message or response.text[:200]


def enqueue_delivery(edition: Edition) -> None:
    from .tasks import deliver_edition

    deliver_edition.enqueue(edition.pk)


def queue_delivery_on_build(sender, edition: Edition, **kwargs) -> None:
    """`edition_built` receiver: send the new edition in its own task."""
    enqueue_delivery(edition)


def resend_delivery(edition: Edition) -> bool:
    """Queue a failed delivery again. False if its delivery had not failed."""
    with transaction.atomic():
        updated = Edition.objects.filter(pk=edition.pk, delivery_status=Edition.Delivery.FAILED).update(
            delivery_status=Edition.Delivery.PENDING, delivery_error=""
        )
        if updated:
            enqueue_delivery(edition)
    return bool(updated)
