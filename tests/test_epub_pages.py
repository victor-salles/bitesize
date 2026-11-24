"""The redesigned book, built from the sample edition."""

import io
import zipfile

import pytest
from PIL import Image

import config
from edition_data import EditionMeta, reading_minutes
from epub import generate_epub
from settings_store import Settings
from sample_edition import NOW, sample_sections


@pytest.fixture(autouse=True)
def pt_br():
    with config.use_settings(Settings(ai_language="pt-BR")):
        yield


def build(tmp_path, **meta) -> zipfile.ZipFile:
    path = tmp_path / "book.epub"
    generate_epub(sample_sections(), {}, {}, path, meta=EditionMeta(now=NOW, **meta))
    return zipfile.ZipFile(path)


def page(book: zipfile.ZipFile, name: str) -> str:
    return book.read(f"EPUB/{name}").decode("utf-8")


@pytest.mark.parametrize("style", ["numero", "jornal", "jornal-invert"])
def test_cover_image_is_three_by_four_in_every_style(tmp_path, style):
    book = build(tmp_path, cover_style=style)
    cover = Image.open(io.BytesIO(book.read("EPUB/cover.jpg")))
    assert cover.size == (1236, 1648)


def test_cover_style_changes_the_cover(tmp_path):
    numero = build(tmp_path, cover_style="numero").read("EPUB/cover.jpg")
    jornal = build(tmp_path, cover_style="jornal").read("EPUB/cover.jpg")
    assert numero != jornal


# ── contents (Opening) ───────────────────────────────────────────────────────

import re


def _text(xhtml: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xhtml)).strip()


def test_contents_is_the_first_page_and_numbers_every_story_across_the_book(tmp_path):
    book = build(tmp_path)
    contents = page(book, "cover.xhtml")
    text = _text(contents)
    assert "Nesta edição" in text
    numbers = re.findall(r'class="toc-num[^"]*">(\d+)<', contents)
    assert numbers == ["01", "02", "03", "04", "05", "06", "07"]
    assert "Story 1" not in text


def test_contents_leads_with_the_headline_and_skips_it_in_its_section(tmp_path):
    contents = page(build(tmp_path), "cover.xhtml")
    text = _text(contents)
    assert text.index("Manchete · Tecnologia · Jornal Exemplo") < text.index("Cidade testa ônibus")
    assert text.count("Cidade testa ônibus elétricos") == 1
    assert "3 matérias · inclui a manchete" in text
    assert "2 matérias" in text
    assert 'href="article_tecnologia_01.xhtml"' in contents
    assert 'href="article_ci_ncia_02.xhtml"' in contents


def test_contents_shows_relevance_reading_time_and_the_running_head(tmp_path):
    contents = page(build(tmp_path), "cover.xhtml")
    text = _text(contents)
    assert re.search(r"Dom · 8 nov 2026 · 7 matérias · \d+ min", text)
    hero_minutes = reading_minutes(sample_sections()["Tecnologia"][0])
    assert f"9,2 · {hero_minutes} min · artigo completo" in text
    assert "Revista Modelo · relevância 8,1" in text
    assert 'src="images/score-09.png"' in contents


def test_contents_section_names_sit_between_wavy_rules(tmp_path):
    book = build(tmp_path)
    contents = page(book, "cover.xhtml")
    assert contents.count('src="images/wave-left.png"') == 3
    assert contents.count('src="images/wave-right.png"') == 3
    assert "EPUB/images/wave-left.png" in book.namelist()


def test_book_uses_grey_tones_only(tmp_path):
    css = build(tmp_path).read("EPUB/style.css").decode()
    colors = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{3,6}\b", css)}
    for color in colors:
        hex6 = color[1:] if len(color) == 7 else "".join(ch * 2 for ch in color[1:])
        r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
        assert r == g == b, color


# ── topics page (TopicsSquares) ──────────────────────────────────────────────

def _spine(book: zipfile.ZipFile) -> list[str]:
    opf = book.read("EPUB/content.opf").decode()
    manifest = dict(re.findall(r'<item[^>]*?href="([^"]+)"[^>]*?id="([^"]+)"', opf))
    by_id = {v: k for k, v in manifest.items()}
    by_id.update({i: h for h, i in re.findall(r'<item[^>]*?id="([^"]+)"[^>]*?href="([^"]+)"', opf)})
    return [by_id.get(i, i) for i in re.findall(r'<itemref[^>]*idref="([^"]+)"', opf)]


def test_topics_page_follows_the_contents(tmp_path):
    book = build(tmp_path)
    spine = [name for name in _spine(book) if name != "nav.xhtml"]
    assert spine[:2] == ["cover.xhtml", "topics.xhtml"]
    assert "EPUB/images/topics.png" in book.namelist()


def test_topics_page_links_every_story_that_mentions_a_topic(tmp_path):
    topics = page(build(tmp_path), "topics.xhtml")
    text = _text(topics)
    assert "Temas da edição" in text
    assert "Tema do dia Tecnologia 27% das menções" in text
    assert "Mais cruzada Matéria 06 em 3 temas" in text
    assert 'src="images/topics.png"' in topics
    tecnologia = re.search(r'Tecnologia</span>(.*?)</p>', topics).group(1)
    assert re.findall(r">(\d\d)</a>", tecnologia) == ["01", "02", "03", "06"]
    assert 'href="cover.xhtml"' in topics and 'href="cover_tecnologia.xhtml"' in topics


def test_topics_page_shows_the_novelty_only_with_a_previous_edition(tmp_path):
    assert "Novidade" not in _text(page(build(tmp_path), "topics.xhtml"))
    with_history = page(build(tmp_path, previous_topic_counts={"tecnologia": 1}), "topics.xhtml")
    assert "Novidade Brasil não apareceu ontem" in _text(with_history)


def test_no_topics_no_topics_page(tmp_path):
    sections = sample_sections()
    for arts in sections.values():
        for art in arts:
            art["temas"] = []
    path = tmp_path / "plain.epub"
    generate_epub(sections, {}, {}, path, meta=EditionMeta(now=NOW))
    assert "EPUB/topics.xhtml" not in zipfile.ZipFile(path).namelist()


# ── section opener (Section.dc.html) ─────────────────────────────────────────

def test_each_section_opens_with_one_page_and_no_paginated_indexes(tmp_path):
    book = build(tmp_path)
    spine = [name for name in _spine(book) if name != "nav.xhtml"]
    assert spine[2:6] == ["cover_tecnologia.xhtml", "article_tecnologia_01.xhtml",
                          "article_tecnologia_02.xhtml", "article_tecnologia_03.xhtml"]
    assert not [name for name in book.namelist() if "/index_" in name]


def test_section_page_has_the_band_the_lead_and_the_other_stories(tmp_path):
    section = page(build(tmp_path), "cover_tecnologia.xhtml")
    text = _text(section)
    minutes = sum(reading_minutes(a) for a in sample_sections()["Tecnologia"])
    assert f"Editoria 1 de 3 3 matérias · {minutes} min" in text
    assert "Jornal Exemplo · Revista Modelo · Portal Fictício" in text
    assert "01 · Destaque · Jornal Exemplo Cidade testa ônibus" in text
    assert re.search(r"02 Revista Modelo Nova bateria .*? Relevância 8,1 · \d+ min · artigo completo", text)
    assert "Relevância 6,4 · 1 min · resumo" in text


def test_section_page_navigation(tmp_path):
    book = build(tmp_path)
    first, last = page(book, "cover_tecnologia.xhtml"), page(book, "cover_economia.xhtml")
    assert 'href="cover.xhtml">← Sumário' in first
    assert ">Começar a ler<" in first and 'href="article_tecnologia_01.xhtml">Começar a ler' in first
    assert 'href="cover_ci_ncia.xhtml">Ciência' in first
    assert "cover_" not in last[last.index('class="page-nav"'):]  # last section: no next one


def test_extra_sections_without_tipo_show_no_tipo(tmp_path):
    sections = sample_sections()
    sections["Calendar"] = [{"title": "Standup", "content": "Daily sync.", "summary": "", "source": "Cal", "url": ""}]
    path = tmp_path / "extras.epub"
    generate_epub(sections, {}, {}, path, meta=EditionMeta(now=NOW))
    text = _text(zipfile.ZipFile(path).read("EPUB/cover_calendar.xhtml").decode())
    assert "resumo" not in text.lower()
