"""The Delivery and Account tabs: a reader's own settings and account."""

from datetime import time

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def ana(db):
    user = User.objects.create_user(username="ana", password="4821")
    user.profile.kindle_email = "ana_42@kindle.com"
    user.profile.save()
    return user


@pytest.fixture
def client_ana(client, ana):
    client.force_login(ana)
    return client


def valid_settings(**overrides) -> dict:
    return {
        "kindle_email": "Ana_New@Kindle.com",
        "delivery_time": "06:30",
        "timezone": "Europe/Lisbon",
        "language": "en",
        **overrides,
    }


@pytest.mark.parametrize("name", ["delivery", "account"])
def test_pages_require_login(client, db, name):
    response = client.get(reverse(name))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse(name)}"


def test_delivery_shows_the_current_settings(client_ana):
    response = client_ana.get(reverse("delivery"))

    form = response.context["form"]
    assert form.initial["kindle_email"] == "ana_42@kindle.com"
    assert form.initial["delivery_time"] == time(7, 0)
    assert form.initial["timezone"] == "America/Sao_Paulo"
    assert form.initial["language"] == "pt-BR"
    assert b'value="07:00"' in response.content


def test_delivery_saves_the_settings(client_ana, ana):
    response = client_ana.post(reverse("delivery"), valid_settings())

    assert response.status_code == 302
    assert response["Location"] == reverse("delivery")
    ana.profile.refresh_from_db()
    assert (
        ana.profile.kindle_email,
        ana.profile.delivery_time,
        ana.profile.timezone,
        ana.profile.language,
    ) == ("ana_new@kindle.com", time(6, 30), "Europe/Lisbon", "en")


def test_delivery_confirms_the_save(client_ana):
    response = client_ana.post(reverse("delivery"), valid_settings(), follow=True)

    assert b"Delivery settings saved." in response.content


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("kindle_email", "ana@gmail.com", "Use your Send-to-Kindle address (ending in @kindle.com or @free.kindle.com)."),
        ("kindle_email", "", "This field is required."),
        ("timezone", "Mars/Olympus", "Unknown time zone: Mars/Olympus"),
        ("delivery_time", "25:00", "Enter a valid time."),
        ("language", "fr", "Select a valid choice. fr is not one of the available choices."),
    ],
)
def test_delivery_rejects_bad_values(client_ana, ana, field, value, error):
    response = client_ana.post(reverse("delivery"), valid_settings(**{field: value}))

    assert response.status_code == 200
    assert response.context["form"].errors[field] == [error]
    ana.profile.refresh_from_db()
    assert ana.profile.kindle_email == "ana_42@kindle.com"


def test_delivery_warns_when_there_is_no_kindle_address(client_ana, ana):
    ana.profile.kindle_email = ""
    ana.profile.save()

    response = client_ana.get(reverse("delivery"))

    assert b"No Kindle address yet: editions have nowhere to go." in response.content


def test_editions_page_links_a_missing_kindle_address_to_delivery(client_ana, ana):
    ana.profile.kindle_email = ""
    ana.profile.save()

    body = client_ana.get(reverse("editions:status")).content.decode()

    assert f'<a href="{reverse("delivery")}">Add your Kindle address</a>' in body


def test_account_shows_the_name_and_a_logout_form(client_ana):
    body = client_ana.get(reverse("account")).content.decode()

    assert "<strong>ana</strong>" in body
    assert f'action="{reverse("logout")}"' in body
    assert reverse("invites") not in body


def test_account_links_staff_to_invites(client, db):
    staff = User.objects.create_user(username="victor", password="x", is_staff=True)
    client.force_login(staff)

    body = client.get(reverse("account")).content.decode()

    assert f'<a href="{reverse("invites")}">Invites</a>' in body
