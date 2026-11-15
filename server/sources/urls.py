from django.urls import path

from . import views

app_name = "sources"

urlpatterns = [
    path("", views.source_list, name="list"),
    path("add/", views.add_source, name="add"),
    path("pick/", views.pick_source, name="pick"),
    path("<int:pk>/toggle/", views.toggle_source, name="toggle"),
    path("<int:pk>/delete/", views.delete_source, name="delete"),
]
