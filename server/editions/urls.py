from django.urls import path

from . import views

app_name = "editions"

urlpatterns = [
    path("", views.status, name="status"),
    path("request/", views.request_today, name="request_today"),
]
