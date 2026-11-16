from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("sources/", include("sources.urls")),
]
