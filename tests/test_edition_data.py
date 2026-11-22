from datetime import datetime

import pytest

import config
from edition_data import (
    StoryNumbers,
    format_reading_time,
    human_published,
    reading_minutes,
    topic_mention_counts,
)
from settings_store import Settings


@pytest.fixture
def pt_br():
    with config.use_settings(Settings(ai_language="pt-BR")):
        yield


@pytest.fixture
def english():
    with config.use_settings(Settings(ai_language="en")):
        yield


def _words(n: int) -> str:
    return " ".join(["palavra"] * n)


def test_reading_minutes_counts_body_words_at_200_per_minute():
    assert reading_minutes({"content": _words(1000)}) == 5
    assert reading_minutes({"content": _words(1001)}) == 6


def test_reading_minutes_is_at_least_one_and_falls_back_to_the_summary():
    assert reading_minutes({"content": "", "summary": "Duas frases curtas."}) == 1
    assert reading_minutes({}) == 1


def test_format_reading_time():
    assert format_reading_time(5) == "5 min"


def test_story_numbers_run_across_sections_in_book_order():
    a, b, c = {"title": "A"}, {"title": "B"}, {"title": "C"}
    numbers = StoryNumbers({"Tecnologia": [a, b], "Ciência": [c], "Vazia": []})
    assert [numbers.label(x) for x in (a, b, c)] == ["01", "02", "03"]
    assert numbers.number(c) == 3
    assert numbers.total == 3


def test_story_numbers_keep_two_digits_minimum_and_grow_past_99():
    arts = [{"title": str(i)} for i in range(100)]
    numbers = StoryNumbers({"X": arts})
    assert numbers.label(arts[8]) == "09"
    assert numbers.label(arts[99]) == "100"


def test_human_published_pt_br(pt_br):
    ts = int(datetime(2026, 11, 8, 6, 30).timestamp())
    assert human_published({"published": "06:30", "published_ts": ts}) == "8 nov, 06:30"


def test_human_published_english(english):
    ts = int(datetime(2026, 11, 8, 6, 30).timestamp())
    assert human_published({"published": "06:30", "published_ts": ts}) == "Nov 8, 06:30"


def test_human_published_without_timestamp_keeps_the_raw_value(pt_br):
    assert human_published({"published": "Sat, 8 Nov"}) == "Sat, 8 Nov"
    assert human_published({}) == ""


def test_topic_mention_counts_count_every_tema_of_every_article_most_first():
    sections = {
        "Tecnologia": [
            {"temas": ["tecnologia", "brasil"]},
            {"temas": ["tecnologia"]},
        ],
        "Ciência": [{"temas": ["ciência", "clima"]}, {"temas": []}, {}],
    }
    counts = topic_mention_counts(sections)
    assert counts == {"tecnologia": 2, "brasil": 1, "ciência": 1, "clima": 1}
    assert list(counts) == ["tecnologia", "brasil", "ciência", "clima"]
