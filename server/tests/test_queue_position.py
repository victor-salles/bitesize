from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django_tasks_db.models import DBTaskResult

from core.models import Edition, Source
from editions.services import DEFAULT_RUN_TIME, QueueStatus, queue_status

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=dt_timezone.utc)
TODAY = date(2026, 11, 15)  # in America/Sao_Paulo (UTC-3) at NOW
MINUTE = timedelta(minutes=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr("django.utils.timezone.now", lambda: NOW)


@pytest.fixture
def ana(db):
    return User.objects.create_user(username="ana", password="1234")


def make_edition(username, status, *, queued_minutes_ago, edition_date=TODAY, **fields):
    user, _ = User.objects.get_or_create(username=username)
    return Edition.objects.create(
        user=user,
        edition_date=edition_date,
        status=status,
        queued_at=NOW - queued_minutes_ago * MINUTE,
        **fields,
    )


def built(username, run_minutes, *, days_ago):
    """A succeeded edition from an earlier day that took `run_minutes` to build."""
    finished = NOW - timedelta(days=days_ago)
    return make_edition(
        username,
        Edition.Status.SUCCEEDED,
        queued_minutes_ago=days_ago * 24 * 60 + run_minutes,
        edition_date=TODAY - timedelta(days=days_ago),
        started_at=finished - run_minutes * MINUTE,
        finished_at=finished,
    )


def test_no_edition_today_has_no_position(ana):
    assert queue_status(ana) == QueueStatus(
        edition=None,
        ahead=None,
        estimated_wait=None,
        typical_run_time=DEFAULT_RUN_TIME,
        from_history=False,
        longer_than_usual=False,
    )


def test_counts_queued_and_running_editions_queued_before_mine(ana):
    built("old", 10, days_ago=1)
    make_edition("bia", Edition.Status.RUNNING, queued_minutes_ago=30, started_at=NOW - 4 * MINUTE)
    make_edition("caio", Edition.Status.QUEUED, queued_minutes_ago=20)
    make_edition("dani", Edition.Status.QUEUED, queued_minutes_ago=10)
    mine = make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=5)
    make_edition("eva", Edition.Status.QUEUED, queued_minutes_ago=1)  # behind me
    make_edition("fabi", Edition.Status.FAILED, queued_minutes_ago=40)  # not in the queue

    # Running one has 6 of its 10 minutes left; two queued ahead and mine take 10 each.
    assert queue_status(ana) == QueueStatus(
        edition=mine,
        ahead=3,
        estimated_wait=36 * MINUTE,
        typical_run_time=10 * MINUTE,
        from_history=True,
        longer_than_usual=True,
    )


def test_first_in_line_waits_one_build(ana):
    built("old", 10, days_ago=1)
    mine = make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=5)

    status = queue_status(ana)

    assert (status.edition, status.ahead, status.estimated_wait, status.longer_than_usual) == (
        mine,
        0,
        10 * MINUTE,
        False,
    )


def test_running_edition_waits_for_what_is_left_of_its_build(ana):
    built("old", 10, days_ago=1)
    make_edition("ana", Edition.Status.RUNNING, queued_minutes_ago=8, started_at=NOW - 7 * MINUTE)

    status = queue_status(ana)

    assert (status.ahead, status.estimated_wait) == (0, 3 * MINUTE)


def test_a_build_running_past_the_typical_time_has_no_time_left(ana):
    built("old", 10, days_ago=1)
    make_edition("ana", Edition.Status.RUNNING, queued_minutes_ago=30, started_at=NOW - 25 * MINUTE)

    assert queue_status(ana).estimated_wait == timedelta(0)


@pytest.mark.parametrize("status", [Edition.Status.SUCCEEDED, Edition.Status.FAILED])
def test_finished_edition_has_no_position(ana, status):
    mine = make_edition("ana", status, queued_minutes_ago=30)

    result = queue_status(ana)

    assert (result.edition, result.ahead, result.estimated_wait) == (mine, None, None)


def test_estimate_uses_the_median_of_recent_succeeded_builds(ana):
    for days_ago, minutes in enumerate([4, 6, 30, 8], start=1):
        built(f"user{days_ago}", minutes, days_ago=days_ago)
    make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=1)

    status = queue_status(ana)

    assert (status.typical_run_time, status.from_history, status.estimated_wait) == (
        7 * MINUTE,
        True,
        7 * MINUTE,
    )


def test_estimate_ignores_failed_builds(ana):
    built("old", 10, days_ago=1)
    make_edition(
        "bia",
        Edition.Status.FAILED,
        queued_minutes_ago=120,
        edition_date=TODAY - timedelta(days=2),
        started_at=NOW - 100 * MINUTE,
        finished_at=NOW - MINUTE,
    )

    assert queue_status(ana).typical_run_time == 10 * MINUTE


def test_estimate_falls_back_to_the_default_without_history(ana):
    make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=1)

    status = queue_status(ana)

    assert (status.typical_run_time, status.from_history, status.estimated_wait) == (
        DEFAULT_RUN_TIME,
        False,
        DEFAULT_RUN_TIME,
    )


def test_today_is_the_users_local_date(ana):
    ana.profile.timezone = "Pacific/Kiritimati"  # UTC+14: already 2026-11-16
    ana.profile.save()
    make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=1)
    tomorrow = make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=1, edition_date=TODAY + timedelta(days=1))

    assert queue_status(ana).edition == tomorrow


# ── Page ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client_ana(client, ana):
    # Requesting an edition needs an active source, so the page tests give Ana one.
    Source.objects.create(user=ana, name="BBC", url="https://bbc.co.uk/ana", category="World")
    client.force_login(ana)
    return client


@pytest.fixture
def client_without_sources(client, ana):
    client.force_login(ana)
    return client


@pytest.mark.parametrize(
    "method, name", [("get", "editions:status"), ("post", "editions:request_today")]
)
def test_pages_require_login(client, db, method, name):
    response = getattr(client, method)(reverse(name))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('login')}?next={reverse(name)}"
    assert not Edition.objects.exists()


def test_home_sends_logged_in_users_to_their_editions(client_ana):
    response = client_ana.get(reverse("home"))

    assert response.status_code == 302
    assert response["Location"] == reverse("editions:status")


def test_empty_state_offers_to_request_todays_edition(client_ana):
    response = client_ana.get(reverse("editions:status"))

    body = response.content.decode()
    assert response.status_code == 200
    assert "No edition for today yet." in body
    assert "You have no editions yet." in body
    assert f'action="{reverse("editions:request_today")}"' in body
    assert "<script" not in body


def test_page_shows_position_estimate_and_busy_warning(client_ana):
    built("old", 10, days_ago=1)
    make_edition("bia", Edition.Status.RUNNING, queued_minutes_ago=30, started_at=NOW - 4 * MINUTE)
    make_edition("caio", Edition.Status.QUEUED, queued_minutes_ago=20)
    make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=5)

    response = client_ana.get(reverse("editions:status"))

    body = response.content.decode()
    assert "Status: Queued" in body
    assert "2 editions ahead of yours." in body
    assert "Estimated wait: about 26 minutes." in body
    assert "Longer than usual: the queue is busy." in body
    assert f'action="{reverse("editions:request_today")}"' not in body


def test_page_says_the_estimate_is_a_guess_without_history(client_ana):
    make_edition("ana", Edition.Status.QUEUED, queued_minutes_ago=1)

    body = client_ana.get(reverse("editions:status")).content.decode()

    assert "You're next." in body
    assert "Estimated wait: about 10 minutes." in body
    assert "No edition has been built yet, so this estimate is a guess." in body
    assert "Longer than usual" not in body


def test_page_lists_only_my_recent_editions(client_ana):
    built("ana", 5, days_ago=2)
    make_edition("ana", Edition.Status.FAILED, queued_minutes_ago=60 * 24, edition_date=date(2026, 11, 14))
    make_edition("bia", Edition.Status.SUCCEEDED, queued_minutes_ago=60, edition_date=date(2026, 11, 10))

    response = client_ana.get(reverse("editions:status"))

    assert [(e.edition_date, e.status) for e in response.context["recent_editions"]] == [
        (date(2026, 11, 14), Edition.Status.FAILED),
        (date(2026, 11, 13), Edition.Status.SUCCEEDED),
    ]
    assert "Nov. 10, 2026" not in response.content.decode()


def test_failed_edition_today_can_be_requested_again(client_ana):
    make_edition("ana", Edition.Status.FAILED, queued_minutes_ago=30)

    body = client_ana.get(reverse("editions:status")).content.decode()

    assert "Status: Failed" in body
    assert f'action="{reverse("editions:request_today")}"' in body


def test_request_queues_todays_edition_once(client_ana, ana):
    first = client_ana.post(reverse("editions:request_today"))
    second = client_ana.post(reverse("editions:request_today"))

    assert first.status_code == second.status_code == 302
    assert first["Location"] == reverse("editions:status")
    assert list(Edition.objects.values_list("user", "edition_date", "status")) == [
        (ana.pk, TODAY, Edition.Status.QUEUED)
    ]
    assert DBTaskResult.objects.count() == 1


def test_request_rejects_get(client_ana):
    assert client_ana.get(reverse("editions:request_today")).status_code == 405


def test_page_without_sources_points_to_sources_instead_of_requesting(client_without_sources):
    body = client_without_sources.get(reverse("editions:status")).content.decode()

    assert "Add at least one active source before requesting an edition." in body
    assert f'href="{reverse("sources:list")}"' in body
    assert f'action="{reverse("editions:request_today")}"' not in body


def test_request_without_sources_queues_nothing(client_without_sources):
    response = client_without_sources.post(reverse("editions:request_today"), follow=True)

    assert response.redirect_chain == [(reverse("editions:status"), 302)]
    assert [str(m) for m in response.context["messages"]] == [
        "Add at least one active source before requesting an edition."
    ]
    assert not Edition.objects.exists()
    assert DBTaskResult.objects.count() == 0
