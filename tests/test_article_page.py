import re

import pytest

import config
from article_page import Block, article_blocks, article_body, is_long
from epub_pages import BookLayout
from sample_edition import sample_sections
from settings_store import Settings


@pytest.fixture(autouse=True)
def pt_br():
    with config.use_settings(Settings(ai_language="pt-BR")):
        yield


def _text(xhtml: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xhtml)).strip()


def _page(category: str, index: int, **changes) -> str:
    sections = sample_sections()
    art = sections[category][index]
    art.update(changes)
    return article_body(art, BookLayout(sections))


def test_short_lines_between_paragraphs_are_subheadings():
    body = "Primeiro parágrafo longo o bastante para ser texto corrido de verdade.\nO sobrevoo\n" \
           "Outro parágrafo que segue o subtítulo com bastante texto corrido."
    assert article_blocks(body) == [
        Block("Primeiro parágrafo longo o bastante para ser texto corrido de verdade."),
        Block("O sobrevoo", heading=True, anchor="parte-1"),
        Block("Outro parágrafo que segue o subtítulo com bastante texto corrido."),
    ]


def test_sentences_and_the_first_line_are_never_subheadings():
    body = "Abertura curta\nUma frase curta.\nParágrafo comprido que fecha o texto com muitas palavras ao final."
    assert not any(block.heading for block in article_blocks(body))


def test_article_header_and_summary_block():
    text = _text(_page("Tecnologia", 0))
    assert text.startswith("01 · Tecnologia 1 de 3 nesta editoria Cidade testa ônibus")
    assert "Jornal Exemplo · 8 nov, 06:30 · 2 min" in text
    assert re.search(r"Resumo Relevância 9,2 Piloto de seis meses .*? Artigo completo tecnologia brasil", text)


def test_drop_cap_on_every_article_even_without_a_summary():
    assert 'class="lede"' in _page("Economia", 1, summary="")


def test_short_article_has_no_outline_and_navigates_to_the_next_story():
    page = _page("Tecnologia", 0)
    text = _text(page)
    assert "Neste artigo" not in text and "A seguir" not in text
    assert "Fonte original: jornalexemplo.com.br/onibus-noturno" in text
    assert 'href="cover_tecnologia.xhtml"' in page and 'href="cover.xhtml"' in page
    assert re.search(r'href="article_tecnologia_02.xhtml">02 Próxima', page)


def test_long_article_gets_key_points_an_outline_and_an_ending():
    sections = sample_sections()
    art = sections["Ciência"][0]
    assert is_long(art)
    page = article_body(art, BookLayout(sections))
    text = _text(page)
    assert "Leitura longa" in text and "palavras" in text
    assert "Pontos-chave Relevância 8,8 1 Imagens de alta resolução" in text
    assert "Piloto" not in text and "Imagens mostram jatos" not in text  # key points replace the summary
    assert re.findall(r'href="#(parte-\d)"', page) == ["parte-1", "parte-2", "parte-3"]
    assert "3 de 3 Próximos passos" in text
    assert 'src="images/end-mark.png"' in page
    assert 'href="#top"' in page
    assert re.search(r"A seguir · 05 · Ciência · \d+ min Recife artificial", text)


def test_long_article_from_an_old_cache_row_falls_back_to_the_summary():
    sections = sample_sections()
    art = sections["Ciência"][0]
    del art["key_points"]
    text = _text(article_body(art, BookLayout(sections)))
    assert "Pontos-chave" not in text
    assert "Resumo" in text and "Imagens mostram jatos" in text


def test_last_story_has_no_next_link():
    page = _page("Economia", 1)
    assert "Próxima" not in _text(page)
