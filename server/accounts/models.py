"""Invites: sign-up is open only to people Victor sends a link to."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def new_token() -> str:
    return secrets.token_urlsafe(32)


def default_expiry():
    return timezone.now() + timedelta(days=settings.INVITE_DAYS)


class InviteUnavailable(Exception):
    """The invite is unknown, used, revoked or expired."""


class InviteQuerySet(models.QuerySet):
    def usable(self):
        return self.filter(used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now())


class Invite(models.Model):
    """A single-use sign-up link."""

    token = models.CharField(max_length=64, unique=True, default=new_token, editable=False)
    note = models.CharField(max_length=120, blank=True, help_text="Who it is for.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invite"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = InviteQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invite for {self.note or 'anyone'} ({self.status})"

    @property
    def status(self) -> str:
        if self.used_at:
            return "used"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "pending"


def redeem_invite(token: str, form):
    """Create the user from a valid SignupForm and spend the invite, atomically.

    The conditional UPDATE claims the invite before the user exists, so two
    sign-ups racing on one token cannot both succeed: the loser updates zero
    rows. If creating the user fails, the transaction undoes the claim.
    """
    with transaction.atomic():
        now = timezone.now()
        claimed = Invite.objects.usable().filter(token=token).update(used_at=now)
        if not claimed:
            raise InviteUnavailable
        user = form.save()
        Invite.objects.filter(token=token).update(used_by=user)
    return user
