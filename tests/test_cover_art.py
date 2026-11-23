from PIL import Image
import io

import pytest

from cover_art import (
    COVER_HEIGHT,
    COVER_STYLES,
    COVER_WIDTH,
    CoverData,
    CoverDesk,
    CoverTeaser,
    CoverTopic,
    render_cover,
)

DATA = CoverData(
    headline="Cidade testa ônibus elétricos sem motorista em linha noturna",
    section="Tecnologia",
    source="Jornal Exemplo",
    dek="Piloto de seis meses cobre 12 km entre o centro e o aeroporto.",
    relevance=9.2,
    relevance_label="9,2",
    weekday="domingo",
    date_line="8 de novembro de 2026",
    day="08",
    month="nov",
    year="2026",
    stats_line="7 matérias · 21 min",
    edition_label="Edição 312",
    teasers=[
        CoverTeaser("02", "Ciência · Revista Modelo", "Sonda registra gêiseres de gelo em lua de Saturno",
                    "Gêiseres em Saturno", "3 min"),
        CoverTeaser("03", "Tecnologia · Revista Modelo", "Nova bateria de sódio promete carga em dez minutos",
                    "Bateria de sódio", "4 min"),
    ],
    desks=[CoverDesk("Tecnologia", 3, "Bateria de sódio carrega em dez minutos"),
           CoverDesk("Ciência", 2, "Gêiseres de gelo em lua de Saturno")],
    topics=[CoverTopic("Tecnologia", 4, "29%"), CoverTopic("Ciência", 3, "21%"), CoverTopic("Clima", 1, "7%")],
    topics_note="14 menções · 7 matérias",
)


def _image(data: bytes) -> Image.Image:
    assert data[:2] == b"\xff\xd8"
    return Image.open(io.BytesIO(data))


def test_cover_is_three_by_four_like_the_kindle_screen():
    assert (COVER_WIDTH, COVER_HEIGHT) == (1236, 1648)
    assert COVER_WIDTH * 4 == COVER_HEIGHT * 3


@pytest.mark.parametrize("style", COVER_STYLES)
def test_every_style_renders_a_full_size_grey_jpeg(style):
    img = _image(render_cover(DATA, style))
    assert img.size == (COVER_WIDTH, COVER_HEIGHT)
    # Grey tones only: JPEG noise aside, red, green and blue stay together.
    rgb = img.convert("RGB").resize((124, 165))
    assert max(max(px) - min(px) for px in rgb.get_flattened_data()) < 24


def test_numero_puts_the_black_block_on_top_and_jornal_starts_white():
    numero = _image(render_cover(DATA, "numero")).convert("L")
    jornal = _image(render_cover(DATA, "jornal")).convert("L")
    invert = _image(render_cover(DATA, "jornal-invert")).convert("L")
    assert numero.getpixel((COVER_WIDTH - 5, 5)) < 30
    assert jornal.getpixel((5, 5)) > 225
    assert invert.getpixel((5, 5)) < 30


def test_unknown_style_falls_back_to_numero():
    assert render_cover(DATA, "nope") == render_cover(DATA, "numero")


def test_cover_renders_without_optional_parts():
    bare = CoverData(headline="Só a manchete")
    for style in COVER_STYLES:
        assert _image(render_cover(bare, style)).size == (COVER_WIDTH, COVER_HEIGHT)
