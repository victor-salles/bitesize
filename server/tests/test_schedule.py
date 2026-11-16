from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django_tasks_db.models import DBTaskResult

from core.models import Edition, Source
from editions.schedule import enqueue_due_editions

# 2026-11-15 10:00 UTC is 07:00 in São Paulo, 11:00 in Lisbon and 19:00 in Tokyo.
MORNING_UTC = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)


def make_reader(username, *, timezone="America/Sao_Paulo", delivery=time(7, 0), kindle=True, sources=True):
    user = User.objects.create_user(username=username, password="1234")
    profile = user.profile
    profile.timezone = timezone
    profile.delivery_time = delivery
    profile.kindle_email = f"{username}@kindle.com" if kindle else ""
    profile.save()
    if sources:
        Source.objects.create(user=user, name="BBC", url=f"https://bbc.co.uk/{username}", category="World")
    return user


def editions():
    return sorted(Edition.objects.values_list("user__username", "edition_date"))


def queued_tasks():
    return DBTaskResult.objects.ready().count()


@pytest.fixture
def three_readers(db):
    return [
        make_reader("ana", timezone="America/Sao_Paulo", delivery=time(7, 0)),
        make_reader("bia", timezone="Europe/Lisbon", delivery=time(7, 0)),
        make_reader("kei", timezone="Asia/Tokyo", delivery=time(7, 0)),
    ]


def run_every_ten_minutes(start, end):
    moment = start
    while moment <= end:
        enqueue_due_editions(moment)
        moment += timedelta(minutes=10)


@pytest.mark.django_db
def test_three_time_zones_each_get_one_edition_per_local_day(three_readers):
    # Two full UTC days of cron runs, every ten minutes.
    run_every_ten_minutes(datetime(2026, 11, 14, 0, 0, tzinfo=UTC), datetime(2026, 11, 15, 23, 50, tzinfo=UTC))

    assert editions() == [
        # The first run is 21:00 on the 13th in São Paulo, past 07:00.
        ("ana", date(2026, 11, 13)),
        ("ana", date(2026, 11, 14)),
        ("ana", date(2026, 11, 15)),
        ("bia", date(2026, 11, 14)),
        ("bia", date(2026, 11, 15)),
        # 07:00 in Tokyo is 22:00 UTC the day before.
        ("kei", date(2026, 11, 14)),
        ("kei", date(2026, 11, 15)),
        ("kei", date(2026, 11, 16)),
    ]
    assert queued_tasks() == 8


@pytest.mark.django_db
def test_enqueues_on_the_local_date_once_delivery_time_has_passed(three_readers):
    enqueued = enqueue_due_editions(MORNING_UTC)

    assert sorted((edition.user.username, edition.edition_date) for edition in enqueued) == [
        ("ana", date(2026, 11, 15)),
        ("bia", date(2026, 11, 15)),
        ("kei", date(2026, 11, 15)),
    ]


@pytest.mark.django_db
def test_waits_until_delivery_time(db):
    make_reader("ana", timezone="America/Sao_Paulo", delivery=time(7, 1))

    assert enqueue_due_editions(MORNING_UTC) == []
    assert editions() == []


@pytest.mark.django_db
def test_enqueues_at_exactly_delivery_time(db):
    make_reader("ana", timezone="America/Sao_Paulo", delivery=time(7, 0))

    enqueue_due_editions(MORNING_UTC)

    assert editions() == [("ana", date(2026, 11, 15))]


@pytest.mark.django_db
def test_running_again_the_same_day_enqueues_nothing(three_readers):
    enqueue_due_editions(MORNING_UTC)

    assert enqueue_due_editions(MORNING_UTC.replace(hour=12)) == []
    assert queued_tasks() == 3


@pytest.mark.django_db
def test_skips_a_user_who_already_has_an_edition_for_the_day(db):
    ana = make_reader("ana")
    Edition.objects.create(user=ana, edition_date=date(2026, 11, 15), status=Edition.Status.QUEUED)

    assert enqueue_due_editions(MORNING_UTC) == []
    assert queued_tasks() == 0


@pytest.mark.django_db
def test_does_not_retry_a_failed_edition(db):
    ana = make_reader("ana")
    Edition.objects.create(user=ana, edition_date=date(2026, 11, 15), status=Edition.Status.FAILED, error="boom")

    assert enqueue_due_editions(MORNING_UTC) == []
    assert Edition.objects.get().status == Edition.Status.FAILED
    assert queued_tasks() == 0


@pytest.mark.django_db
def test_skips_a_user_without_active_sources(db, caplog):
    ana = make_reader("ana", sources=False)
    Source.objects.create(user=ana, name="Off", url="https://off.example/feed", category="World", active=False)

    with caplog.at_level("INFO", logger="editions.schedule"):
        assert enqueue_due_editions(MORNING_UTC) == []

    assert editions() == []
    assert caplog.messages == ["Not scheduling ana's edition for 2026-11-15: no active sources"]


@pytest.mark.django_db
def test_skips_a_user_without_a_kindle_address(db, caplog):
    make_reader("ana", kindle=False)

    with caplog.at_level("INFO", logger="editions.schedule"):
        assert enqueue_due_editions(MORNING_UTC) == []

    assert editions() == []
    assert caplog.messages == ["Not scheduling ana's edition for 2026-11-15: no Kindle address"]


@pytest.mark.django_db
def test_skips_inactive_users(db):
    ana = make_reader("ana")
    ana.is_active = False
    ana.save()

    assert enqueue_due_editions(MORNING_UTC) == []


@pytest.mark.django_db
def test_command_uses_the_current_time_and_reports_the_count(three_readers):
    out = StringIO()

    with mock.patch("editions.schedule.timezone.now", return_value=MORNING_UTC):
        call_command("enqueue_due_editions", stdout=out)

    assert out.getvalue() == "Enqueued 3 edition(s).\n"
    assert editions() == [
        ("ana", date(2026, 11, 15)),
        ("bia", date(2026, 11, 15)),
        ("kei", date(2026, 11, 15)),
    ]
