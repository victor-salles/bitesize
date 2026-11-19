from unittest import mock

import pytest
from django.db.utils import OperationalError
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.content == b"ok\n"
    assert response["Content-Type"].startswith("text/plain")


def test_healthz_route_name_resolves():
    assert reverse("healthz") == "/healthz"


@pytest.mark.django_db
def test_healthz_reports_503_when_database_fails(client):
    with mock.patch("core.views.connection.cursor", side_effect=OperationalError("down")):
        response = client.get("/healthz")

    assert response.status_code == 503


@pytest.mark.django_db
def test_healthz_rejects_post(client):
    assert client.post("/healthz").status_code == 405


@pytest.mark.django_db
def test_healthz_answers_plain_http_when_https_is_enforced(client, settings):
    """Dokku and uptime probes may call the container over plain HTTP."""
    settings.SECURE_SSL_REDIRECT = True  # off in settings_test so other tests use plain http

    assert client.get("/healthz").status_code == 200
    assert client.get("/login/").status_code == 301
