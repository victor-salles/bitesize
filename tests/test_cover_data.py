import pytest

import config
from cover_data import build_cover_data, stats_line
from edition_data import EditionMeta, StoryNumbers
from settings_store import Settings
from sample_edition import NOW, sample_sections


@pytest.fixture(autouse=True)
def pt_br():
    with config.use_settings(Settings(ai_language="pt-BR")):
        yield


def _cover(edition_number=None):
    sections = sample_sections()
    hero = sections["Tecnologia"][0]
    return build_cover_data(
        sections, hero["title"], hero, "Tecnologia", StoryNumbers(sections),
        EditionMeta(now=NOW, edition_number=edition_number),
    )


def test_cover_data_shows_the_day_and_the_edition_totals():
    data = _cover(edition_number=312)
    assert (data.weekday, data.day, data.month, data.year) == ("domingo", "08", "nov", "2026")
    assert data.date_line == "8 de novembro de 2026"
    assert data.edition_label == "Edição 312"
    assert data.stats_line == stats_line(sample_sections())
    assert data.stats_line.startswith("7 matérias · ")


def test_cover_data_hides_the_edition_number_without_history():
    assert _cover().edition_label == ""


def test_cover_data_headline_kicker_and_relevance():
    data = _cover()
    assert (data.section, data.source) == ("Tecnologia", "Jornal Exemplo")
    assert data.relevance == pytest.approx(9.2)
    assert data.relevance_label == "9,2"
    assert data.dek == "Piloto de seis meses cobre 12 km entre o centro e o aeroporto, com um operador a bordo."


def test_cover_teasers_are_the_top_stories_after_the_headline_with_their_book_numbers():
    teasers = _cover().teasers
    assert [(t.number, t.short_title) for t in teasers] == [
        ("04", "Gêiseres em Saturno"),
        ("02", "Bateria de sódio"),
        ("06", "Feiras de bairro passam…"),
    ]
    assert teasers[0].kicker == "Ciência · Revista Modelo"


def test_cover_desks_count_each_section_and_skip_the_headline_in_the_lead():
    desks = _cover().desks
    assert [(d.name, d.count, d.lead) for d in desks] == [
        ("Tecnologia", 3, "Bateria de sódio"),
        ("Ciência", 2, "Gêiseres em Saturno"),
        ("Economia", 2, "Feiras de bairro passam a aceitar pagamento…"),
    ]


def test_cover_topics_count_mentions():
    data = _cover()
    assert data.topics_note == "15 menções · 7 matérias"
    assert [(t.name, t.count, t.percent) for t in data.topics][:2] == [("Tecnologia", 4, "27%"), ("Brasil", 3, "20%")]
