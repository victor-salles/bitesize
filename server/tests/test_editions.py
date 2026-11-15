from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

import pipeline
from core.models import Edition, Source
from editions.services import enqueue_edition, retry_edition
from editions.signals import edition_built
from editions.tasks import build_user_edition

DAY = date(2026, 11, 14)


@pytest.fixture(autouse=True)
def editions_dir(settings, tmp_path):
    settings.EDITIONS_DIR = tmp_path / "editions"
    return settings.EDITIONS_DIR


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Replace pipeline.build_edition; records each config and writes no EPUB unless told to."""

    class Fake:
        calls: list = []
        error: Exception | None = None
        write_epub = True

        def __call__(self, config):
            self.calls.append(config)
            if self.error:
                raise self.error
            epub = Path(config.output_dir) / "digest.epub" if self.write_epub else None
            return pipeline.EditionResult(
                epub_path=epub,
                raw_count=10,
                full_text_count=8,
                kept_count=6,
                filtered_count=4,
                article_count=6,
                section_counts={"World": 6},
            )

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(pipeline, "build_edition", fake)
    return fake


def make_user(username, *, sources=True):
    user = User.objects.create_user(username=username, password="1234")
    if sources:
        Source.objects.create(user=user, name="BBC", url=f"https://bbc.co.uk/{username}", category="World")
    return user


@pytest.fixture
def ana(db):
    return make_user("ana")


def run_worker():
    call_command("db_worker", batch=True, startup_delay=False, reload=False, interval=0, verbosity=0)


def ready_tasks():
    return DBTaskResult.objects.ready()


# ── enqueue ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_enqueue_creates_a_queued_edition_and_one_task(ana):
    edition = enqueue_edition(ana, DAY)

    assert edition.status == Edition.Status.QUEUED
    assert edition.edition_date == DAY
    task = ready_tasks().get()
    assert task.task_path == "editions.tasks.build_user_edition"
    assert task.args_kwargs["args"] == [edition.pk]


@pytest.mark.django_db
def test_enqueue_twice_reuses_the_edition_and_queues_once(ana):
    first = enqueue_edition(ana, DAY)
    second = enqueue_edition(ana, DAY)

    assert first.pk == second.pk
    assert Edition.objects.count() == 1
    assert ready_tasks().count() == 1


@pytest.mark.django_db
def test_enqueue_does_not_rebuild_a_succeeded_edition(ana):
    Edition.objects.create(user=ana, edition_date=DAY, status=Edition.Status.SUCCEEDED)

    edition = enqueue_edition(ana, DAY)

    assert edition.status == Edition.Status.SUCCEEDED
    assert not ready_tasks().exists()


@pytest.mark.django_db
def test_enqueue_requeues_a_failed_edition(ana):
    old = timezone.now() - timedelta(hours=3)
    failed = Edition.objects.create(
        user=ana,
        edition_date=DAY,
        status=Edition.Status.FAILED,
        queued_at=old,
        started_at=old,
        finished_at=old,
        error="boom",
    )

    edition = enqueue_edition(ana, DAY)

    assert edition.pk == failed.pk
    assert edition.status == Edition.Status.QUEUED
    assert edition.error == ""
    assert edition.started_at is None and edition.finished_at is None
    assert edition.queued_at > old
    assert ready_tasks().count() == 1


# ── run ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_run_builds_the_edition_from_the_users_profile_and_sources(ana, fake_pipeline, editions_dir):
    ana.profile.language = "en"
    ana.profile.save()
    built = []
    edition_built.connect(lambda sender, edition, **kw: built.append(edition.pk), weak=False, dispatch_uid="t")
    try:
        edition = enqueue_edition(ana, DAY)
        run_worker()
    finally:
        edition_built.disconnect(dispatch_uid="t")

    edition.refresh_from_db()
    assert edition.status == Edition.Status.SUCCEEDED
    assert edition.error == ""
    assert edition.started_at <= edition.finished_at
    assert edition.article_count == 6
    assert edition.section_counts == {"World": 6}

    (config,) = fake_pipeline.calls
    assert config.sources == {"World": {"BBC": "https://bbc.co.uk/ana"}}
    assert config.language == "en"
    assert config.ai is None  # shared default client until #65
    assert Path(config.output_dir) == editions_dir / str(ana.pk) / "2026-11-14"
    assert Path(config.output_dir).is_dir()
    assert edition.epub_path == str(Path(config.output_dir) / "digest.epub")
    assert built == [edition.pk]


@pytest.mark.django_db
def test_run_failure_keeps_the_error_and_the_next_edition_still_runs(fake_pipeline, monkeypatch):
    ana, bia = make_user("ana"), make_user("bia")
    first = enqueue_edition(ana, DAY)
    second = enqueue_edition(bia, DAY)

    def fail_first(config):
        if not fake_pipeline.calls:
            fake_pipeline.calls.append(config)
            raise RuntimeError("feed exploded")
        fake_pipeline.calls.append(config)
        return pipeline.EditionResult(epub_path=Path(config.output_dir) / "d.epub", article_count=1)

    monkeypatch.setattr(pipeline, "build_edition", fail_first)
    run_worker()

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == Edition.Status.FAILED
    assert "feed exploded" in first.error
    assert first.finished_at is not None
    assert second.status == Edition.Status.SUCCEEDED


@pytest.mark.django_db
def test_run_fails_when_the_pipeline_writes_no_epub(ana, fake_pipeline):
    fake_pipeline.write_epub = False
    edition = enqueue_edition(ana, DAY)

    run_worker()

    edition.refresh_from_db()
    assert edition.status == Edition.Status.FAILED
    assert "no EPUB" in edition.error
    assert edition.raw_count == 10


@pytest.mark.django_db
def test_run_fails_without_active_sources(fake_pipeline, db):
    user = make_user("ana", sources=False)
    edition = enqueue_edition(user, DAY)

    run_worker()

    edition.refresh_from_db()
    assert edition.status == Edition.Status.FAILED
    assert "No active sources" in edition.error
    assert fake_pipeline.calls == []


@pytest.mark.django_db
def test_retry_runs_a_failed_edition_again(ana, fake_pipeline):
    fake_pipeline.error = RuntimeError("down")
    edition = enqueue_edition(ana, DAY)
    run_worker()
    edition.refresh_from_db()
    assert edition.status == Edition.Status.FAILED

    fake_pipeline.error = None
    assert retry_edition(edition) is True
    run_worker()

    edition.refresh_from_db()
    assert edition.status == Edition.Status.SUCCEEDED
    assert edition.error == ""
    assert len(fake_pipeline.calls) == 2


@pytest.mark.django_db
def test_retry_ignores_editions_that_have_not_failed(ana):
    edition = enqueue_edition(ana, DAY)

    assert retry_edition(edition) is False
    assert ready_tasks().count() == 1


# ── order and one at a time ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_editions_run_in_queued_order(fake_pipeline):
    users = [make_user(name) for name in ("ana", "bia", "cris")]
    for user in users:
        enqueue_edition(user, DAY)

    run_worker()

    assert [c.sources["World"]["BBC"].rsplit("/", 1)[1] for c in fake_pipeline.calls] == ["ana", "bia", "cris"]
    started = [e.started_at for e in Edition.objects.order_by("queued_at")]
    assert started == sorted(started)


@pytest.mark.django_db
def test_a_retried_edition_goes_to_the_back_of_the_queue(fake_pipeline):
    ana, bia = make_user("ana"), make_user("bia")
    old = timezone.now() - timedelta(hours=1)
    Edition.objects.create(user=ana, edition_date=DAY, status=Edition.Status.FAILED, queued_at=old)
    enqueue_edition(bia, DAY)

    retry_edition(Edition.objects.get(user=ana))
    run_worker()

    assert [c.sources["World"]["BBC"].rsplit("/", 1)[1] for c in fake_pipeline.calls] == ["bia", "ana"]


@pytest.mark.django_db
@pytest.mark.parametrize("status", [Edition.Status.RUNNING, Edition.Status.SUCCEEDED, Edition.Status.FAILED])
def test_task_does_not_rerun_an_edition_that_is_not_queued(ana, fake_pipeline, status):
    edition = Edition.objects.create(user=ana, edition_date=DAY, status=status, started_at=timezone.now())

    assert build_user_edition.call(edition.pk) == "skipped"
    assert fake_pipeline.calls == []
    edition.refresh_from_db()
    assert edition.status == status


@pytest.mark.django_db
def test_task_skips_an_edition_that_no_longer_exists(fake_pipeline):
    assert build_user_edition.call(999) == "skipped"
    assert fake_pipeline.calls == []


@pytest.mark.django_db
def test_task_waits_while_another_edition_is_running(fake_pipeline):
    ana, bia = make_user("ana"), make_user("bia")
    Edition.objects.create(user=ana, edition_date=DAY, status=Edition.Status.RUNNING, started_at=timezone.now())
    waiting = Edition.objects.create(user=bia, edition_date=DAY)

    assert build_user_edition.call(waiting.pk) == "deferred"

    assert fake_pipeline.calls == []
    waiting.refresh_from_db()
    assert waiting.status == Edition.Status.QUEUED
    deferred = DBTaskResult.objects.get()
    assert deferred.args_kwargs["args"] == [waiting.pk]
    assert deferred.run_after > timezone.now()


@pytest.mark.django_db
def test_a_stale_running_edition_is_failed_and_does_not_block(fake_pipeline, settings):
    ana, bia = make_user("ana"), make_user("bia")
    long_ago = timezone.now() - settings.EDITION_STALE_AFTER - timedelta(minutes=1)
    stuck = Edition.objects.create(user=ana, edition_date=DAY, status=Edition.Status.RUNNING, started_at=long_ago)
    waiting = Edition.objects.create(user=bia, edition_date=DAY)

    assert build_user_edition.call(waiting.pk) == "succeeded"

    stuck.refresh_from_db()
    waiting.refresh_from_db()
    assert stuck.status == Edition.Status.FAILED
    assert "stale" in stuck.error.lower()
    assert waiting.status == Edition.Status.SUCCEEDED


# ── admin ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_admin_action_retries_only_failed_editions(admin_client):
    ana, bia = make_user("ana"), make_user("bia")
    failed = Edition.objects.create(user=ana, edition_date=DAY, status=Edition.Status.FAILED, error="x")
    done = Edition.objects.create(user=bia, edition_date=DAY, status=Edition.Status.SUCCEEDED)

    response = admin_client.post(
        reverse("admin:core_edition_changelist"),
        {"action": "retry_failed", "_selected_action": [failed.pk, done.pk]},
        follow=True,
    )

    assert response.status_code == 200
    failed.refresh_from_db()
    done.refresh_from_db()
    assert failed.status == Edition.Status.QUEUED
    assert done.status == Edition.Status.SUCCEEDED
    assert [t.args_kwargs["args"] for t in ready_tasks()] == [[failed.pk]]
    assert "1 failed edition" in response.content.decode()
