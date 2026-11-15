from math import ceil

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_safe

from . import throttle
from .forms import InviteForm, LoginForm, SignupForm
from .models import Invite, InviteUnavailable, redeem_invite

WRONG = "Wrong name or PIN."


def _safe_next(request, url: str) -> str:
    if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, require_https=request.is_secure()):
        return url
    return resolve_url("home")


def _needs_invite(request, status=200):
    # One page for no token, unknown, used, revoked and expired: no hint which.
    return render(request, "accounts/invite_required.html", status=status)


@require_safe
def signup_closed(request):
    if request.user.is_authenticated:
        return redirect("home")
    return _needs_invite(request)


@require_http_methods(["GET", "POST"])
def signup(request, token):
    if request.user.is_authenticated:
        return redirect("home")
    if not Invite.objects.usable().filter(token=token).exists():
        return _needs_invite(request, status=404)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = redeem_invite(token, form)
        except InviteUnavailable:
            return _needs_invite(request, status=404)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("home")
    return render(request, "accounts/signup.html", {"form": form, "token": token})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = LoginForm(request.POST or None, initial={"next": request.GET.get("next", "")})
    status = 200
    if request.method == "POST" and form.is_valid():
        name = form.cleaned_data["name"].strip()
        ip = throttle.client_ip(request)
        if throttle.is_locked(name, ip):
            minutes = ceil(settings.LOGIN_LOCKOUT_SECONDS / 60)
            form.add_error(None, f"Too many failed attempts. Wait {minutes} minutes and try again.")
            status = 429
        else:
            # Names are unique regardless of case; log in with the stored spelling.
            match = User.objects.filter(username__iexact=name).values_list("username", flat=True).first()
            user = authenticate(request, username=match or name, password=form.cleaned_data["pin"])
            if user is not None:
                throttle.clear_account(name)
                login(request, user)
                return redirect(_safe_next(request, form.cleaned_data["next"]))
            throttle.record_failure(name, ip)
            form.add_error(None, WRONG)
    return render(request, "accounts/login.html", {"form": form}, status=status)


@require_safe
@login_required
def home(request):
    return render(request, "accounts/home.html")


def _staff_only(request):
    if not request.user.is_staff:
        raise PermissionDenied


@require_http_methods(["GET", "POST"])
@login_required
def invites(request):
    _staff_only(request)
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        Invite.objects.create(note=form.cleaned_data["note"], created_by=request.user)
        return redirect("invites")
    recent = list(Invite.objects.select_related("used_by")[:50])
    for invite in recent:
        invite.link = request.build_absolute_uri(reverse("signup", args=[invite.token]))
    return render(request, "accounts/invites.html", {"form": form, "invites": recent})


@require_http_methods(["POST"])
@login_required
def revoke_invite(request, pk):
    _staff_only(request)
    invite = get_object_or_404(Invite, pk=pk)
    if invite.status == "pending":
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
    return redirect("invites")
