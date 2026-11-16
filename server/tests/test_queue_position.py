from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth.models import User

from core.models import Edition
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
