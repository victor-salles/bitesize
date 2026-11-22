from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup_closed, name="signup_closed"),
    path("signup/<str:token>/", views.signup, name="signup"),
    path("invites/", views.invites, name="invites"),
    path("invites/<int:pk>/revoke/", views.revoke_invite, name="revoke_invite"),
    path("delivery/", views.delivery, name="delivery"),
    path("account/", views.account, name="account"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
