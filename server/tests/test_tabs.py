"""The shared layout: tab navigation and the design-token stylesheet."""

import re

import pytest
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse

TABS = [
    ("sources:list", "Sources"),
    ("delivery", "Delivery"),
    ("editions:status", "Editions"),
    ("account", "Account"),
]
CURRENT = re.compile(r'<a href="([^"]+)" aria-current="page">')


@pytest.fixture
def ana(db):
    user = User.objects.create_user(username="ana", password="4821")
    user.profile.kindle_email = "ana_42@kindle.com"
    user.profile.save()
    return user


@pytest.fixture
def client_ana(client, ana):
    client.force_login(ana)
    return client


def current_tabs(body: str) -> list[str]:
    return CURRENT.findall(body)


@pytest.mark.parametrize(("url_name", "label"), TABS)
def test_each_tab_renders_and_marks_itself_current(client_ana, url_name, label):
    response = client_ana.get(reverse(url_name))

    body = response.content.decode()
    assert response.status_code == 200
    assert current_tabs(body) == [reverse(url_name)]
    assert f'<a href="{reverse(url_name)}" aria-current="page">{label}</a>' in body
    assert "<script" not in body


def test_every_tab_links_to_every_section_in_order(client_ana):
    body = client_ana.get(reverse("editions:status")).content.decode()

    nav = body.split('<nav class="tabs"')[1].split("</nav>")[0]
    assert re.findall(r'<a href="([^"]+)"', nav) == [reverse(name) for name, _ in TABS]


def test_invites_page_belongs_to_the_account_tab(client, db):
    staff = User.objects.create_user(username="victor", password="x", is_staff=True)
    client.force_login(staff)

    body = client.get(reverse("invites")).content.decode()

    assert current_tabs(body) == [reverse("account")]


@pytest.mark.parametrize("page", ["login", "signup_closed"])
def test_logged_out_pages_use_the_base_without_tabs(client, db, page):
    body = client.get(reverse(page)).content.decode()

    assert 'class="tabs"' not in body
    assert "bitesize/site.css" in body


def test_layout_links_the_design_token_stylesheet(client_ana):
    body = client_ana.get(reverse("account")).content.decode()

    assert '<link rel="stylesheet" href="/static/bitesize/site.css">' in body


def test_stylesheet_defines_the_design_tokens():
    css = open(finders.find("bitesize/site.css"), encoding="utf-8").read()

    for token in ("--font-reading", "--text-body", "--space-3", "--border-thick", "--tap-target"):
        assert f"{token}:" in css
