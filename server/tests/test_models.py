from datetime import date, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import LANGUAGES, Article, Edition, Profile, Source


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ana", password="1234")


# ── Profile ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_is_created_with_the_user(user):
    profile = Profile.objects.get(user=user)

    assert user.profile == profile
    assert profile.language == "pt-BR"
    assert profile.timezone == "America/Sao_Paulo"
    assert profile.delivery_time == time(7, 0)
    assert profile.kindle_email == ""
    assert profile.sender_approved is False


@pytest.mark.django_db
def test_saving_the_user_again_keeps_one_profile(user):
    user.first_name = "Ana"
    user.save()

    assert Profile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email", ["ana@kindle.com", "ana_42@free.kindle.com", "Ana@Kindle.COM"]
)
def test_kindle_email_accepts_amazon_addresses(user, email):
    user.profile.kindle_email = email
    user.profile.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email", ["ana@gmail.com", "ana@notkindle.com", "ana@kindle.com.evil.io", "not-an-email"]
)
def test_kindle_email_rejects_other_addresses(user, email):
    user.profile.kindle_email = email

    with pytest.raises(ValidationError) as exc:
        user.profile.full_clean()
    assert "kindle_email" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("tz", ["UTC", "Europe/Lisbon", "America/New_York"])
def test_timezone_accepts_iana_names(user, tz):
    user.profile.timezone = tz
    user.profile.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("tz", ["Mars/Olympus", "GMT+3", "", "../etc/passwd"])
def test_timezone_rejects_unknown_names(user, tz):
    user.profile.timezone = tz

    with pytest.raises(ValidationError) as exc:
        user.profile.full_clean()
    assert "timezone" in exc.value.message_dict


@pytest.mark.django_db
def test_language_rejects_values_the_pipeline_does_not_know(user):
    user.profile.language = "fr"

    with pytest.raises(ValidationError) as exc:
        user.profile.full_clean()
    assert "language" in exc.value.message_dict


def test_languages_match_the_pipeline():
    import ai_locale

    assert {code for code, _ in LANGUAGES} == set(ai_locale.LANGUAGE_LABELS)


# ── Source ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_source_url_is_unique_per_user(user):
    Source.objects.create(user=user, name="BBC", url="https://bbc.co.uk/rss", category="World")

    with pytest.raises(IntegrityError), transaction.atomic():
        Source.objects.create(user=user, name="BBC 2", url="https://bbc.co.uk/rss", category="News")


@pytest.mark.django_db
def test_two_users_can_follow_the_same_feed(user):
    other = User.objects.create_user(username="bia", password="5678")
    Source.objects.create(user=user, name="BBC", url="https://bbc.co.uk/rss", category="World")
    Source.objects.create(user=other, name="BBC", url="https://bbc.co.uk/rss", category="World")

    assert Source.objects.count() == 2


@pytest.mark.django_db
def test_source_requires_a_valid_url(user):
    source = Source(user=user, name="Bad", url="not a url", category="World")

    with pytest.raises(ValidationError) as exc:
        source.full_clean()
    assert "url" in exc.value.message_dict


@pytest.mark.django_db
def test_edition_sources_groups_active_sources_by_category(user):
    other = User.objects.create_user(username="bia", password="5678")
    Source.objects.create(user=user, name="BBC", url="https://bbc.co.uk/rss", category="World")
    Source.objects.create(user=user, name="NPR", url="https://npr.org/rss", category="World")
    Source.objects.create(user=user, name="Verge", url="https://theverge.com/rss", category="Tech")
    Source.objects.create(
        user=user, name="Off", url="https://off.example/rss", category="Tech", active=False
    )
    Source.objects.create(user=other, name="G1", url="https://g1.globo.com/rss", category="Brazil")

    assert Source.objects.edition_sources(user) == {
        "World": {"BBC": "https://bbc.co.uk/rss", "NPR": "https://npr.org/rss"},
        "Tech": {"Verge": "https://theverge.com/rss"},
    }


@pytest.mark.django_db
def test_edition_sources_is_empty_without_active_sources(user):
    assert Source.objects.edition_sources(user) == {}


@pytest.mark.django_db
def test_edition_sources_fits_edition_config(user, tmp_path):
    from pipeline import EditionConfig

    Source.objects.create(user=user, name="BBC", url="https://bbc.co.uk/rss", category="World")

    config = EditionConfig(
        sources=Source.objects.edition_sources(user),
        output_dir=tmp_path,
        language=user.profile.language,
    )

    assert config.sources == {"World": {"BBC": "https://bbc.co.uk/rss"}}
    assert config.effective_settings().ai_language == "pt-BR"


# ── Edition ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_new_edition_is_queued_now(user):
    before = timezone.now()
    edition = Edition.objects.create(user=user, edition_date=date(2026, 11, 14))

    assert edition.status == Edition.Status.QUEUED
    assert edition.delivery_status == Edition.Delivery.PENDING
    assert before <= edition.queued_at <= timezone.now()
    assert edition.started_at is None
    assert edition.finished_at is None
    assert edition.section_counts == {}


@pytest.mark.django_db
def test_one_edition_per_user_per_date(user):
    Edition.objects.create(user=user, edition_date=date(2026, 11, 14))

    with pytest.raises(IntegrityError), transaction.atomic():
        Edition.objects.create(user=user, edition_date=date(2026, 11, 14))


@pytest.mark.django_db
def test_other_users_and_dates_get_their_own_edition(user):
    other = User.objects.create_user(username="bia", password="5678")
    Edition.objects.create(user=user, edition_date=date(2026, 11, 14))
    Edition.objects.create(user=user, edition_date=date(2026, 11, 15))
    Edition.objects.create(user=other, edition_date=date(2026, 11, 14))

    assert Edition.objects.count() == 3


@pytest.mark.django_db
def test_record_result_copies_the_pipeline_stats(user):
    edition = Edition.objects.create(user=user, edition_date=date(2026, 11, 14))
    result = SimpleNamespace(
        epub_path=Path("/app/data/editions/ana.epub"),
        raw_count=40,
        full_text_count=30,
        kept_count=20,
        filtered_count=10,
        article_count=18,
        section_counts={"World": 10, "Tech": 8},
        topic_counts={"política": 3, "economia": 1},
    )

    edition.record_result(result)
    edition.refresh_from_db()

    assert edition.epub_path == "/app/data/editions/ana.epub"
    assert edition.raw_count == 40
    assert edition.full_text_count == 30
    assert edition.kept_count == 20
    assert edition.filtered_count == 10
    assert edition.article_count == 18
    assert edition.section_counts == {"World": 10, "Tech": 8}
    assert edition.topic_counts == {"política": 3, "economia": 1}


@pytest.mark.django_db
def test_record_result_without_epub_leaves_path_blank(user):
    edition = Edition.objects.create(user=user, edition_date=date(2026, 11, 14))

    edition.record_result(SimpleNamespace(epub_path=None, section_counts={}))
    edition.refresh_from_db()

    assert edition.epub_path == ""
    assert edition.article_count == 0


@pytest.mark.django_db
def test_run_time_is_known_only_once_finished(user):
    edition = Edition.objects.create(user=user, edition_date=date(2026, 11, 14))
    assert edition.run_time is None

    edition.started_at = timezone.now()
    assert edition.run_time is None

    edition.finished_at = edition.started_at + timedelta(minutes=3)
    assert edition.run_time == timedelta(minutes=3)


@pytest.mark.django_db
def test_editions_list_newest_date_first(user):
    old = Edition.objects.create(user=user, edition_date=date(2026, 11, 13))
    new = Edition.objects.create(user=user, edition_date=date(2026, 11, 14))

    assert list(Edition.objects.all()) == [new, old]


# ── Article ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_article_is_cached_once_per_url_and_language():
    Article.objects.create(url="https://bbc.co.uk/news/1", language="pt-BR", title="Um")

    with pytest.raises(IntegrityError), transaction.atomic():
        Article.objects.create(url="https://bbc.co.uk/news/1", language="pt-BR", title="Dois")


@pytest.mark.django_db
def test_same_article_can_be_cached_in_another_language():
    Article.objects.create(url="https://bbc.co.uk/news/1", language="pt-BR", title="Um")
    Article.objects.create(url="https://bbc.co.uk/news/1", language="en", title="One")

    assert Article.objects.count() == 2


@pytest.mark.django_db
def test_article_defaults():
    article = Article.objects.create(url="https://bbc.co.uk/news/1", language="en", title="One")

    assert article.summary == ""
    assert article.score is None
    assert article.text_length == 0
    assert article.created_at is not None
    assert article.updated_at is not None


# ── Admin ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("model", ["profile", "source", "edition", "article"])
def test_admin_changelist_renders(admin_client, model, user):
    Source.objects.create(user=user, name="BBC", url="https://bbc.co.uk/rss", category="World")
    Edition.objects.create(user=user, edition_date=date(2026, 11, 14))
    Article.objects.create(url="https://bbc.co.uk/news/1", language="en", title="One")

    response = admin_client.get(f"/admin/core/{model}/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_migrations_match_the_models():
    from django.core.management import call_command

    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
