"""Error pages use the shared layout."""

import re

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.views.defaults import server_error

CURRENT = re.compile(r'aria-current="page"')


@pytest.fixture
def client_ana(client, db):
    client.force_login(User.objects.create_user(username="ana", password="4821"))
    return client


def test_unknown_page_shows_the_not_found_page_with_tabs(client_ana):
    response = client_ana.get("/no-such-page/")

    body = response.content.decode()
    assert response.status_code == 404
    assert "Page not found" in body
    assert 'class="tabs"' in body
    assert not CURRENT.search(body)


def test_server_error_page_renders_without_a_request_context():
    response = server_error(RequestFactory().get("/"))

    assert response.status_code == 500
    assert b"Something went wrong" in response.content
    assert b'class="tabs"' not in response.content
