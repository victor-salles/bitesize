from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    # The admin's own login has no PIN lockout (accounts.throttle); staff log in
    # on the throttled page, which honours ?next= back into the admin.
    path(f"{settings.ADMIN_URL}login/", RedirectView.as_view(pattern_name="login", query_string=True)),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("sources/", include("sources.urls")),
]
