import importlib.util
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse

from accounts.forms import SignupForm
from accounts.models import Invite
from accounts.throttle import client_ip

SIGNUP = {"name": "Ana", "kindle_email": "ana_42@kindle.com", "pin": "4821", "pin_confirm": "4821"}


@pytest.fixture(autouse=True)
def empty_cache(db):
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def ana(db):
    user = User.objects.create_user(username="Ana", password="4821")
    user.profile.kindle_email = "ana_42@kindle.com"
    user.profile.save()
    return user


@pytest.fixture
def signup_url(db):
    return reverse("signup", args=[Invite.objects.create(note="Ana").token])


def login(client, name="Ana", pin="4821", **extra):
    return client.post(reverse("login"), {"name": name, "pin": pin}, **extra)


# ── Sign-up ──────────────────────────────────────────────────────────────────


def test_signup_page_renders_a_csrf_protected_form(client, signup_url):
    response = client.get(signup_url)

    assert response.status_code == 200
    assert b"csrfmiddlewaretoken" in response.content
    assert b"<script" not in response.content


def test_signup_creates_the_user_with_a_hashed_pin_and_kindle_email(client, signup_url):
    response = client.post(signup_url, SIGNUP)

    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    user = User.objects.get(username="Ana")
    assert user.password != "4821"
    assert user.check_password("4821")
    assert user.profile.kindle_email == "ana_42@kindle.com"


def test_signup_logs_the_user_in(client, signup_url):
    client.post(signup_url, SIGNUP)

    response = client.get(reverse("home"), follow=True)

    assert response.status_code == 200
    assert b"Ana" in response.content


def test_signup_lowercases_the_kindle_email(client, signup_url):
    client.post(signup_url, {**SIGNUP, "kindle_email": "Ana_42@Kindle.COM"})

    assert User.objects.get(username="Ana").profile.kindle_email == "ana_42@kindle.com"


def test_signup_rejects_a_taken_name_in_any_case(ana):
    form = SignupForm(data={**SIGNUP, "name": "ANA"})

    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.parametrize("name", ["", "a", "ana maria", "x" * 31, "ana<script>"])
def test_signup_rejects_bad_names(db, name):
    form = SignupForm(data={**SIGNUP, "name": name})

    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.parametrize("email", ["ana@gmail.com", "ana@kindle.com.evil.com", "not-an-email", ""])
def test_signup_rejects_non_kindle_emails(db, email):
    form = SignupForm(data={**SIGNUP, "kindle_email": email})

    assert not form.is_valid()
    assert "kindle_email" in form.errors


def test_signup_accepts_free_kindle_addresses(db):
    assert SignupForm(data={**SIGNUP, "kindle_email": "ana@free.kindle.com"}).is_valid()


# ── PIN validation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("pin", ["4821", "48213", "482139"])
def test_pin_accepts_four_to_six_digits(db, pin):
    assert SignupForm(data={**SIGNUP, "pin": pin, "pin_confirm": pin}).is_valid()


@pytest.mark.parametrize("pin", ["", "482", "4821390", "48a1", "48 21", "４８２１", "-4821"])
def test_pin_rejects_anything_but_four_to_six_ascii_digits(db, pin):
    form = SignupForm(data={**SIGNUP, "pin": pin, "pin_confirm": pin})

    assert not form.is_valid()
    assert "pin" in form.errors


@pytest.mark.parametrize("pin", ["0000", "1111", "1234", "4321", "123456", "987654", "0123"])
def test_pin_rejects_trivial_pins(db, pin):
    form = SignupForm(data={**SIGNUP, "pin": pin, "pin_confirm": pin})

    assert not form.is_valid()
    assert "pin" in form.errors


def test_pin_must_match_its_confirmation(db):
    form = SignupForm(data={**SIGNUP, "pin_confirm": "4822"})

    assert not form.is_valid()
    assert "pin_confirm" in form.errors


# ── Login and logout ─────────────────────────────────────────────────────────


def test_login_page_renders_a_csrf_protected_form(client):
    response = client.get(reverse("login"))

    assert b"Forgot your PIN" in response.content

    assert response.status_code == 200
    assert b"csrfmiddlewaretoken" in response.content
    assert b'inputmode="numeric"' in response.content


def test_login_with_name_and_pin(client, ana):
    response = login(client)

    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert client.session["_auth_user_id"] == str(ana.pk)


def test_login_name_is_case_insensitive(client, ana):
    response = login(client, name="  aNA ")

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(ana.pk)


@pytest.mark.parametrize(("name", "pin"), [("Ana", "4822"), ("Bia", "4821")])
def test_login_rejects_a_wrong_pin_or_name_with_one_message(client, ana, name, pin):
    response = login(client, name=name, pin=pin)

    assert response.status_code == 200
    assert b"Wrong name or PIN" in response.content
    assert "_auth_user_id" not in client.session


def test_login_rejects_inactive_users(client, ana):
    ana.is_active = False
    ana.save()

    response = login(client)

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_follows_a_safe_next_url(client, ana):
    response = client.post(reverse("login"), {"name": "Ana", "pin": "4821", "next": "/admin/"})

    assert response["Location"] == "/admin/"


def test_login_ignores_an_offsite_next_url(client, ana):
    response = client.post(reverse("login"), {"name": "Ana", "pin": "4821", "next": "https://evil.example/"})

    assert response["Location"] == reverse("home")


def test_login_and_signup_require_csrf(ana, signup_url):
    from django.test import Client

    strict = Client(enforce_csrf_checks=True)

    assert strict.post(reverse("login"), {"name": "Ana", "pin": "4821"}).status_code == 403
    assert strict.post(signup_url, {**SIGNUP, "name": "Bia"}).status_code == 403
    assert strict.post(reverse("logout")).status_code == 403


def test_logout_ends_the_session(client, ana):
    client.force_login(ana)

    response = client.post(reverse("logout"))

    assert response.status_code == 302
    assert response["Location"] == reverse("login")
    assert "_auth_user_id" not in client.session


def test_logout_refuses_get(client, ana):
    client.force_login(ana)

    assert client.get(reverse("logout")).status_code == 405
    assert client.session["_auth_user_id"] == str(ana.pk)


# ── Redirects ────────────────────────────────────────────────────────────────


def test_home_requires_login(client):
    response = client.get(reverse("home"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


@pytest.mark.parametrize("page", ["login", "signup_closed"])
def test_authenticated_users_are_sent_home(client, ana, page):
    client.force_login(ana)

    response = client.get(reverse(page))

    assert response.status_code == 302
    assert response["Location"] == reverse("home")


def test_home_shows_the_kindle_email_and_a_logout_form(client, ana):
    client.force_login(ana)

    response = client.get(reverse("home"), follow=True)

    assert b"ana_42@kindle.com" in response.content
    assert f'action="{reverse("logout")}"'.encode() in response.content


# ── Session lifetime ─────────────────────────────────────────────────────────


def test_session_lasts_a_year_by_default(client, ana):
    login(client)

    year = 365 * 24 * 60 * 60
    assert settings.SESSION_COOKIE_AGE == year
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is False
    assert client.session.get_expiry_age() == year
    assert client.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == year


SETTINGS_FILE = Path(__file__).resolve().parents[1] / "bitesize_server" / "settings.py"


def load_settings(monkeypatch, **env):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "s3cr3t")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("bitesize_server._accounts_settings", SETTINGS_FILE)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "bitesize_server"
    spec.loader.exec_module(module)
    return module


def test_session_lifetime_is_configurable(monkeypatch):
    loaded = load_settings(monkeypatch, DJANGO_SESSION_DAYS="30")

    assert loaded.SESSION_COOKIE_AGE == 30 * 24 * 60 * 60


def test_rate_limit_cache_is_shared_between_processes(monkeypatch):
    loaded = load_settings(monkeypatch)

    assert loaded.CACHES["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"


# ── Lockout ──────────────────────────────────────────────────────────────────


def test_account_locks_after_too_many_failures(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 3
    for _ in range(3):
        assert login(client, pin="0001").status_code == 200

    response = login(client)  # the right PIN

    assert response.status_code == 429
    assert b"Too many failed attempts" in response.content
    assert b"Forgot your PIN" in response.content
    assert "_auth_user_id" not in client.session


def test_account_lock_ignores_name_case(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 2
    login(client, name="ana", pin="0001")
    login(client, name="ANA", pin="0001")

    assert login(client).status_code == 429


def test_account_lock_applies_from_every_ip(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 2
    login(client, pin="0001", REMOTE_ADDR="10.0.0.1")
    login(client, pin="0001", REMOTE_ADDR="10.0.0.2")

    assert login(client, REMOTE_ADDR="10.0.0.3").status_code == 429


def test_ip_locks_after_too_many_failures_across_accounts(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 100
    settings.LOGIN_FAILURES_PER_IP = 3
    for name in ["Bia", "Caio", "Duda"]:
        login(client, name=name, pin="0001", REMOTE_ADDR="10.0.0.9")

    assert login(client, REMOTE_ADDR="10.0.0.9").status_code == 429
    assert login(client, REMOTE_ADDR="10.0.0.10").status_code == 302


def test_successful_login_clears_the_account_failures(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 3
    login(client, pin="0001")
    login(client, pin="0001")
    login(client)
    client.post(reverse("logout"))
    login(client, pin="0001")
    login(client, pin="0001")

    assert login(client).status_code == 302


def test_lock_expires_after_the_lockout_window(client, ana, settings):
    settings.LOGIN_FAILURES_PER_ACCOUNT = 1
    settings.LOGIN_LOCKOUT_SECONDS = 1
    login(client, pin="0001")
    assert login(client).status_code == 429

    cache.clear()  # what the timeout does once the window passes

    assert login(client).status_code == 302


def test_failures_are_stored_with_the_lockout_timeout(ana, client, settings, monkeypatch):
    settings.LOGIN_LOCKOUT_SECONDS = 123
    calls = []
    real_set = cache.set
    monkeypatch.setattr(cache, "set", lambda *a, **kw: calls.append(kw.get("timeout")) or real_set(*a, **kw))

    login(client, pin="0001")

    assert calls and all(timeout == 123 for timeout in calls)


# ── Client IP ────────────────────────────────────────────────────────────────


def test_client_ip_uses_the_address_the_proxy_saw(rf):
    request = rf.get("/", REMOTE_ADDR="172.17.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7")

    assert client_ip(request) == "203.0.113.7"


def test_client_ip_falls_back_to_remote_addr(rf):
    assert client_ip(rf.get("/", REMOTE_ADDR="203.0.113.7")) == "203.0.113.7"


@pytest.mark.parametrize("value", ["abc", "0", "-3"])
def test_settings_reject_a_bad_integer(monkeypatch, value):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured, match="DJANGO_SESSION_DAYS"):
        load_settings(monkeypatch, DJANGO_SESSION_DAYS=value)
