from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
]
