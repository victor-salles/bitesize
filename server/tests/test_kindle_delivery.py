"""Emailing built editions to the reader's Kindle through Resend (#66)."""

import base64
from datetime import date, datetime
from datetime import timezone as dt_timezone

import pytest
import requests
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from core.models import Edition
from editions import delivery
from editions.services import build_claimed_edition
from editions.tasks import deliver_edition

DAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 9, 30, tzinfo=dt_timezone.utc)
EPUB_BYTES = b"PK\x03\x04 a tiny epub"


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


@pytest.fixture
def resend(monkeypatch, settings):
    """Replace requests.post in the delivery module; records each call and answers with `response`."""
    settings.RESEND_API_KEY = "re_test_key"
    settings.DELIVERY_FROM_EMAIL = "BiteSIze <bitesize@victorsalles.com>"

    class Fake:
        calls: list = []
        response = FakeResponse(200, {"id": "email-1"})
        error: Exception | None = None

        def __call__(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if self.error:
                raise self.error
            return self.response

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(delivery.requests, "post", fake)
    return fake


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    return NOW


def built_edition(tmp_path, *, kindle_email="ana_42@kindle.com", username="ana", epub=EPUB_BYTES):
    user = User.objects.create_user(username=username, password="4821")
    user.profile.kindle_email = kindle_email
    user.profile.save()
    epub_path = ""
    if epub is not None:
        path = tmp_path / f"{username}.epub"
        path.write_bytes(epub)
        epub_path = str(path)
    return Edition.objects.create(
        user=user, edition_date=DAY, status=Edition.Status.SUCCEEDED, epub_path=epub_path
    )


def delivery_tasks():
    return DBTaskResult.objects.ready().filter(task_path="editions.tasks.deliver_edition")


# ── sending ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_delivery_emails_the_epub_to_the_kindle_address(tmp_path, resend, frozen_now):
    edition = built_edition(tmp_path)

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.DELIVERED
    assert resend.calls == [
        (
            "https://api.resend.com/emails",
            {
                "headers": {"Authorization": "Bearer re_test_key"},
                "json": {
                    "from": "BiteSIze <bitesize@victorsalles.com>",
                    "to": ["ana_42@kindle.com"],
                    "subject": "BiteSIze – 14 de novembro de 2026",
                    "text": "Your BiteSIze edition for 2026-11-14 is attached.",
                    "attachments": [
                        {
                            "filename": "BiteSIze – 14 de novembro de 2026.epub",
                            "content": base64.b64encode(EPUB_BYTES).decode("ascii"),
                        }
                    ],
                },
                "timeout": 60,
            },
        )
    ]
    edition.refresh_from_db()
    assert (edition.delivery_status, edition.delivered_at, edition.delivery_error) == (
        Edition.Delivery.DELIVERED,
        NOW,
        "",
    )


@pytest.mark.django_db
def test_delivery_records_the_api_error(tmp_path, resend):
    resend.response = FakeResponse(
        422, {"statusCode": 422, "name": "validation_error", "message": "Invalid `to` field."}
    )
    edition = built_edition(tmp_path)

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    edition.refresh_from_db()
    assert (edition.delivery_status, edition.delivered_at, edition.delivery_error) == (
        Edition.Delivery.FAILED,
        None,
        "Resend answered 422: Invalid `to` field.",
    )


@pytest.mark.django_db
def test_delivery_records_an_api_error_without_json(tmp_path, resend):
    resend.response = FakeResponse(502, text="Bad Gateway")
    edition = built_edition(tmp_path)

    deliver_edition.call(edition.pk)

    edition.refresh_from_db()
    assert edition.delivery_error == "Resend answered 502: Bad Gateway"


@pytest.mark.django_db
def test_delivery_records_a_network_error(tmp_path, resend):
    resend.error = requests.ConnectionError("connection refused")
    edition = built_edition(tmp_path)

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    edition.refresh_from_db()
    assert edition.delivery_error == "Could not reach Resend: ConnectionError: connection refused"


@pytest.mark.django_db
def test_delivery_fails_without_an_api_key(tmp_path, resend, settings):
    settings.RESEND_API_KEY = ""
    edition = built_edition(tmp_path)

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    assert resend.calls == []
    edition.refresh_from_db()
    assert (edition.delivery_status, edition.delivery_error) == (
        Edition.Delivery.FAILED,
        "RESEND_API_KEY is not set, so the server cannot send email.",
    )


@pytest.mark.django_db
def test_delivery_fails_without_a_kindle_address(tmp_path, resend):
    edition = built_edition(tmp_path, kindle_email="")

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    assert resend.calls == []
    edition.refresh_from_db()
    assert edition.delivery_error == "No Kindle address: add one on the Delivery tab."


@pytest.mark.django_db
def test_delivery_fails_when_the_epub_is_missing(tmp_path, resend):
    edition = built_edition(tmp_path)
    edition.epub_path = str(tmp_path / "gone.epub")
    edition.save()

    deliver_edition.call(edition.pk)

    assert resend.calls == []
    edition.refresh_from_db()
    assert edition.delivery_error == f"EPUB not found at {tmp_path / 'gone.epub'}."


@pytest.mark.django_db
def test_delivery_fails_when_the_epub_is_too_large(tmp_path, resend, monkeypatch):
    monkeypatch.setattr(delivery, "MAX_EMAIL_BYTES", 8)  # 6 bytes of EPUB at most
    edition = built_edition(tmp_path, epub=b"1234567")

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    assert resend.calls == []
    edition.refresh_from_db()
    assert edition.delivery_error == (
        "The EPUB is too large to email: 7 bytes, over the 6-byte limit "
        "(Resend takes 8 bytes per email after base64 encoding)."
    )


def test_the_size_limit_fits_resend_and_kindle():
    # Resend: 40 MB per email after base64. Kindle: 50 MB per document.
    assert delivery.MAX_EMAIL_BYTES == 40 * 1024 * 1024
    assert delivery.max_epub_bytes() == 31457280
    assert len(base64.b64encode(b"x" * delivery.max_epub_bytes())) <= delivery.MAX_EMAIL_BYTES


@pytest.mark.django_db
def test_an_unexpected_error_marks_the_delivery_failed(tmp_path, resend, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(delivery, "send_epub", broken)
    edition = built_edition(tmp_path)

    result = deliver_edition.call(edition.pk)

    assert result == Edition.Delivery.FAILED
    edition.refresh_from_db()
    assert edition.delivery_error == "RuntimeError: boom"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "delivery_status"),
    [
        (Edition.Status.FAILED, Edition.Delivery.PENDING),
        (Edition.Status.SUCCEEDED, Edition.Delivery.DELIVERED),
        (Edition.Status.SUCCEEDED, Edition.Delivery.FAILED),
    ],
)
def test_delivery_skips_editions_that_are_not_waiting_to_be_sent(tmp_path, resend, status, delivery_status):
    edition = built_edition(tmp_path)
    Edition.objects.filter(pk=edition.pk).update(status=status, delivery_status=delivery_status)

    assert deliver_edition.call(edition.pk) == "skipped"
    assert resend.calls == []


@pytest.mark.django_db
def test_delivery_skips_an_edition_that_no_longer_exists(resend):
    assert deliver_edition.call(999) == "skipped"
    assert resend.calls == []


# ── hook into the build ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_built_edition_queues_its_delivery(tmp_path, monkeypatch, settings):
    import pipeline

    settings.EDITIONS_DIR = tmp_path / "editions"
    edition = built_edition(tmp_path)
    Edition.objects.filter(pk=edition.pk).update(status=Edition.Status.RUNNING)
    edition.refresh_from_db()
    monkeypatch.setattr("editions.services.edition_config", lambda edition: type("C", (), {"sources": {"W": {}}})())
    monkeypatch.setattr(
        pipeline, "build_edition", lambda config: pipeline.EditionResult(epub_path=tmp_path / "ana.epub")
    )

    assert build_claimed_edition(edition) == Edition.Status.SUCCEEDED

    assert [task.args_kwargs["args"] for task in delivery_tasks()] == [[edition.pk]]


# ── admin ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_admin_action_resends_only_failed_deliveries(tmp_path, admin_client):
    failed = built_edition(tmp_path, username="ana")
    done = built_edition(tmp_path, username="bia")
    Edition.objects.filter(pk=failed.pk).update(delivery_status=Edition.Delivery.FAILED, delivery_error="x")
    Edition.objects.filter(pk=done.pk).update(delivery_status=Edition.Delivery.DELIVERED)

    response = admin_client.post(
        reverse("admin:core_edition_changelist"),
        {"action": "resend_delivery", "_selected_action": [failed.pk, done.pk]},
        follow=True,
    )

    assert response.status_code == 200
    failed.refresh_from_db()
    done.refresh_from_db()
    assert (failed.delivery_status, failed.delivery_error) == (Edition.Delivery.PENDING, "")
    assert done.delivery_status == Edition.Delivery.DELIVERED
    assert [task.args_kwargs["args"] for task in delivery_tasks()] == [[failed.pk]]
    content = response.content.decode()
    assert "Queued 1 failed delivery again." in content
    assert "Skipped 1 edition(s) whose delivery had not failed." in content


# ── pages ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_editions_page_shows_the_delivery_status(tmp_path, client, monkeypatch):
    edition = built_edition(tmp_path)
    Edition.objects.filter(pk=edition.pk).update(
        delivery_status=Edition.Delivery.FAILED, delivery_error="Resend answered 422: Invalid `to` field."
    )
    monkeypatch.setattr("editions.views.local_today", lambda user: DAY)
    monkeypatch.setattr("editions.services.local_today", lambda user: DAY)
    client.force_login(edition.user)

    content = client.get(reverse("editions:status")).content.decode()

    assert "<p>Delivery: Failed</p>" in content
    assert "<p>Resend answered 422: Invalid `to` field.</p>" in content
    assert "<th>Delivery</th>" in content
    assert "<td>Failed</td>" in content


@pytest.mark.django_db
def test_delivery_tab_asks_to_approve_the_sender(client, settings):
    settings.DELIVERY_FROM_EMAIL = "BiteSIze <bitesize@victorsalles.com>"
    user = User.objects.create_user(username="ana", password="4821")
    client.force_login(user)

    content = client.get(reverse("delivery")).content.decode()

    assert (
        "<p>Add <strong>bitesize@victorsalles.com</strong> to Amazon's "
        "Approved Personal Document E-mail List, or your Kindle will not accept editions.</p>"
    ) in content
