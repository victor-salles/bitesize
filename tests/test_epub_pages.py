"""The redesigned book, built from the sample edition."""

import io
import zipfile

import pytest
from PIL import Image

import config
from edition_data import EditionMeta
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
