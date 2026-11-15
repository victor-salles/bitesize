from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from accounts.forms import SignupForm
from accounts.models import Invite, InviteUnavailable, redeem_invite

SIGNUP = {"name": "Bia", "kindle_email": "bia@kindle.com", "pin": "4821", "pin_confirm": "4821"}
NEEDS_INVITE = b"You need an invite from Victor"


@pytest.fixture
def victor(db):
    return User.objects.create_user(username="victor", password="a-long-staff-password", is_staff=True)


@pytest.fixture
def staff_client(client, victor):
    client.force_login(victor)
    return client


@pytest.fixture
def invite(victor):
    return Invite.objects.create(note="Bia", created_by=victor)


def signup_url(invite):
    return reverse("signup", args=[invite.token])


# ── Model ────────────────────────────────────────────────────────────────────


def test_invite_tokens_are_long_and_unique(db):
    first, second = Invite.objects.create(), Invite.objects.create()

    assert len(first.token) >= 40
    assert first.token != second.token


def test_invite_expires_after_fourteen_days_by_default(db):
    invite = Invite.objects.create()

    assert abs(invite.expires_at - (timezone.now() + timedelta(days=14))) < timedelta(minutes=1)


def test_invite_lifetime_is_configurable(db, settings):
    settings.INVITE_DAYS = 3

    invite = Invite.objects.create()

    assert abs(invite.expires_at - (timezone.now() + timedelta(days=3))) < timedelta(minutes=1)


def test_invite_status(invite, victor):
    assert invite.status == "pending"
    invite.revoked_at = timezone.now()
    assert invite.status == "revoked"
    invite.revoked_at = None
    invite.expires_at = timezone.now() - timedelta(seconds=1)
    assert invite.status == "expired"
    invite.used_at, invite.used_by = timezone.now(), victor
    assert invite.status == "used"


# ── Staff page ───────────────────────────────────────────────────────────────


def test_invites_page_requires_login(client):
    response = client.get(reverse("invites"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


def test_invites_page_is_staff_only(client, db):
    client.force_login(User.objects.create_user(username="ana", password="4821"))

    assert client.get(reverse("invites")).status_code == 403
    assert client.post(reverse("invites"), {"note": "x"}).status_code == 403
    assert not Invite.objects.exists()


def test_staff_creates_an_invite_and_sees_the_full_link(staff_client, victor):
    response = staff_client.post(reverse("invites"), {"note": "Bia"}, follow=True)

    invite = Invite.objects.get()
    assert invite.note == "Bia"
    assert invite.created_by == victor
    assert f"http://testserver/signup/{invite.token}/".encode() in response.content
    assert b"pending" in response.content
    assert b"csrfmiddlewaretoken" in response.content
    assert b"<script" not in response.content


def test_invites_page_lists_each_status(staff_client, victor):
    Invite.objects.create(note="used one", used_at=timezone.now(), used_by=victor)
    Invite.objects.create(note="old one", expires_at=timezone.now() - timedelta(days=1))
    Invite.objects.create(note="revoked one", revoked_at=timezone.now())

    content = staff_client.get(reverse("invites")).content

    for status in (b"used", b"expired", b"revoked"):
        assert status in content


def test_staff_revokes_an_invite(staff_client, invite):
    response = staff_client.post(reverse("revoke_invite", args=[invite.pk]))

    assert response.status_code == 302
    invite.refresh_from_db()
    assert invite.status == "revoked"


def test_revoke_is_staff_only_and_post_only(client, staff_client, invite):
    assert staff_client.get(reverse("revoke_invite", args=[invite.pk])).status_code == 405
    client.logout()
    client.force_login(User.objects.create_user(username="ana", password="4821"))

    assert client.post(reverse("revoke_invite", args=[invite.pk])).status_code == 403
    invite.refresh_from_db()
    assert invite.status == "pending"


def test_revoking_a_used_invite_changes_nothing(staff_client, invite, victor):
    invite.used_at, invite.used_by = timezone.now(), victor
    invite.save()

    staff_client.post(reverse("revoke_invite", args=[invite.pk]))

    invite.refresh_from_db()
    assert invite.status == "used"


# ── Sign-up with an invite ───────────────────────────────────────────────────


def test_plain_signup_needs_an_invite(client, db):
    response = client.get(reverse("signup_closed"))

    assert response.status_code == 200
    assert NEEDS_INVITE in response.content
    assert b"<form" not in response.content.split(b"<main>")[1]


def test_signup_with_a_valid_invite(client, invite):
    assert client.get(signup_url(invite)).status_code == 200

    response = client.post(signup_url(invite), SIGNUP)

    assert response.status_code == 302
    user = User.objects.get(username="Bia")
    invite.refresh_from_db()
    assert invite.status == "used"
    assert invite.used_by == user
    assert invite.used_at is not None


def test_an_invite_works_only_once(client, invite):
    client.post(signup_url(invite), SIGNUP)
    client.logout()

    response = client.post(signup_url(invite), {**SIGNUP, "name": "Caio"})

    assert NEEDS_INVITE in response.content
    assert not User.objects.filter(username="Caio").exists()


def make_expired(invite):
    invite.expires_at = timezone.now() - timedelta(seconds=1)
    invite.save()


def make_revoked(invite):
    invite.revoked_at = timezone.now()
    invite.save()


@pytest.mark.parametrize("spoil", [make_expired, make_revoked])
def test_expired_or_revoked_invites_are_refused(client, invite, spoil):
    spoil(invite)

    get = client.get(signup_url(invite))
    post = client.post(signup_url(invite), SIGNUP)

    for response in (get, post):
        assert response.status_code == 404
        assert NEEDS_INVITE in response.content
    assert not User.objects.filter(username="Bia").exists()


def test_unknown_and_spoiled_invites_look_the_same(client, invite):
    unknown = client.get(reverse("signup", args=["no-such-token"]))
    make_expired(invite)
    expired = client.get(signup_url(invite))

    assert unknown.status_code == expired.status_code == 404
    assert unknown.content == expired.content


def test_redeeming_is_single_use_even_after_both_forms_validated(invite):
    # Two sign-ups that both passed validation before either saved.
    first = SignupForm(data=SIGNUP)
    second = SignupForm(data={**SIGNUP, "name": "Caio"})
    assert first.is_valid() and second.is_valid()

    redeem_invite(invite.token, first)
    with pytest.raises(InviteUnavailable):
        redeem_invite(invite.token, second)

    assert list(User.objects.order_by("pk").values_list("username", flat=True)) == ["victor", "Bia"]


def test_a_failed_signup_leaves_the_invite_unused(invite, monkeypatch):
    form = SignupForm(data=SIGNUP)
    assert form.is_valid()
    monkeypatch.setattr(SignupForm, "save", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        redeem_invite(invite.token, form)

    invite.refresh_from_db()
    assert invite.status == "pending"


# ── PIN reset by Victor in the admin ─────────────────────────────────────────


def test_admin_can_reset_a_users_pin(client, db):
    admin = User.objects.create_superuser(username="root", password="a-long-staff-password")
    ana = User.objects.create_user(username="ana", password="4821")
    client.force_login(admin)

    response = client.post(
        reverse("admin:auth_user_password_change", args=[ana.pk]),
        {"usable_password": "true", "password1": "5937", "password2": "5937"},
    )

    assert response.status_code == 302
    ana.refresh_from_db()
    assert ana.check_password("5937")


def test_admin_pin_reset_still_refuses_trivial_pins(client, db):
    admin = User.objects.create_superuser(username="root", password="a-long-staff-password")
    ana = User.objects.create_user(username="ana", password="4821")
    client.force_login(admin)

    response = client.post(
        reverse("admin:auth_user_password_change", args=[ana.pk]),
        {"usable_password": "true", "password1": "1234", "password2": "1234"},
    )

    assert response.status_code == 200
    ana.refresh_from_db()
    assert ana.check_password("4821")


def test_staff_passwords_keep_the_strong_validators(client, db):
    admin = User.objects.create_superuser(username="root", password="a-long-staff-password")
    client.force_login(admin)

    response = client.post(
        reverse("admin:auth_user_password_change", args=[admin.pk]),
        {"usable_password": "true", "password1": "5937", "password2": "5937"},
    )

    assert response.status_code == 200
    admin.refresh_from_db()
    assert admin.check_password("a-long-staff-password")


def test_invites_are_in_the_admin(client, db, invite):
    admin = User.objects.create_superuser(username="root", password="a-long-staff-password")
    client.force_login(admin)

    assert client.get(reverse("admin:accounts_invite_changelist")).status_code == 200
