import io

import pytest
from PIL import Image

import config
from epub_pages import BookLayout
from settings_store import Settings
from sample_edition import sample_sections
from topics_chart import ChartRow, render_topics_chart
from topics_page import Trend, topics_data


@pytest.fixture(autouse=True)
def pt_br():
    with config.use_settings(Settings(ai_language="pt-BR")):
        yield


def _data(previous=None):
    sections = sample_sections()
    return topics_data(BookLayout(sections), previous)


def test_rows_count_mentions_and_list_the_stories_that_mention_each_topic():
    rows = _data().rows
    assert [(r.name, r.count) for r in rows] == [
        ("Tecnologia", 4), ("Brasil", 3), ("Ciência", 3), ("Clima", 2), ("Economia", 2), ("Mundo", 1),
    ]
    assert rows[0].story_numbers == ["01", "02", "03", "06"]
    assert rows[0].percent_long == "26,7%"
    assert rows[0].percent_short == "27%"
    assert _data().total == 15


def test_cards_pick_the_topic_of_the_day_and_the_most_crossed_story():
    data = _data()
    assert (data.topic_of_day.name, data.topic_of_day.percent_short) == ("Tecnologia", "27%")
    assert data.most_crossed_number == "06"
    assert data.most_crossed_topics == 3


def test_without_a_previous_edition_there_is_no_trend_and_no_novelty():
    data = _data(previous=None)
    assert all(row.trend is None for row in data.rows)
    assert data.novelty is None


def test_trend_compares_with_the_previous_edition():
    data = _data(previous={"tecnologia": 2, "brasil": 3, "ciência": 5, "economia": 2, "mundo": 4})
    trends = {row.name: row.trend for row in data.rows}
    assert trends["Tecnologia"] == Trend("up", 2)
    assert trends["Brasil"] == Trend("same", 0)
    assert trends["Ciência"] == Trend("down", -2)
    assert trends["Clima"] == Trend("new", 0)
    assert data.novelty.name == "Clima"


def test_ties_get_a_note():
    notes = {row.name: row.note for row in _data().rows}
    assert notes["Brasil"] == "empate com Ciência"
    assert notes["Ciência"] == "empate com Brasil"
    assert notes["Mundo"] == ""


def test_chart_is_a_grey_png_sized_for_the_kindle_page():
    rows = [ChartRow("Tecnologia", 4, "27%", "26,7%", ["01", "02", "03", "06"], Trend("up", 2), "", "+2"),
            ChartRow("Clima", 1, "7%", "6,7%", ["05"], Trend("new", 0), "", "novo")]
    png = render_topics_chart(rows, total=5, headers=("Todas as menções", "5 · 1 quadrado = 1 menção",
                                                       "Tema", "vs. ontem", "Nº", "%"))
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.size[0] == 1200
    rgb = img.convert("RGB").resize((120, img.size[1] // 10))
    assert all(max(p) - min(p) < 8 for p in rgb.get_flattened_data())


def test_chart_handles_many_mentions():
    rows = [ChartRow(f"T{i}", 20, "17%", "16,7%", [f"{n:02d}" for n in range(20)], None, "", "") for i in range(6)]
    png = render_topics_chart(rows, total=120, headers=("a", "b", "c", "d", "e", "f"))
    assert Image.open(io.BytesIO(png)).size[0] == 1200
