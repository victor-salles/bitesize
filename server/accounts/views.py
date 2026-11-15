from math import ceil

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_safe

from . import throttle
from .forms import LoginForm, SignupForm

WRONG = "Wrong name or PIN."


def _safe_next(request, url: str) -> str:
    if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, require_https=request.is_secure()):
        return url
    return resolve_url("home")


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("home")
    return render(request, "accounts/signup.html", {"form": form})


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
