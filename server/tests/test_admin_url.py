import importlib

import pytest
from django.contrib.auth.models import User
from django.urls import clear_url_caches, reverse

from bitesize_server import urls


@pytest.fixture
def admin_at(settings):
    """Rebuild the URLconf with the admin mounted at `path`."""

    def mount(path):
        settings.ADMIN_URL = path
        importlib.reload(urls)
        clear_url_caches()

    yield mount
    settings.ADMIN_URL = "admin/"
    importlib.reload(urls)
    clear_url_caches()


def test_admin_defaults_to_admin_path():
    assert reverse("admin:index") == "/admin/"


@pytest.mark.django_db
def test_admin_moves_to_the_configured_path(client, admin_at):
    admin_at("back-office-7f3a/")

    assert reverse("admin:index") == "/back-office-7f3a/"
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_admin_is_staff_only(client):
    client.force_login(User.objects.create_user(username="ana", password="x"))

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('admin:login')}?next={reverse('admin:index')}"


@pytest.mark.django_db
def test_admin_opens_for_staff(client):
    client.force_login(User.objects.create_user(username="boss", password="x", is_staff=True))

    assert client.get(reverse("admin:index")).status_code == 200


@pytest.mark.django_db
def test_admin_login_goes_through_the_throttled_login(client):
    """Django's admin login has no lockout; staff sign in on the PIN login page instead."""
    response = client.get(f"{reverse('admin:login')}?next=/admin/")

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next=/admin/"


@pytest.mark.django_db
def test_admin_login_refuses_posted_credentials(client):
    staff = User.objects.create_user(username="boss", password="correct horse battery", is_staff=True)

    response = client.post(reverse("admin:login"), {"username": "boss", "password": "correct horse battery"})

    assert response.status_code == 302
    assert response["Location"] == reverse("login")
    assert "_auth_user_id" not in client.session
    staff.refresh_from_db()
    assert staff.last_login is None
