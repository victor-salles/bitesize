from PIL import Image, ImageDraw

from fonts import FONT_DIR, fraunces, inter


def test_embedded_fonts_ship_with_their_ofl_licenses():
    for name in ("Fraunces-OFL.txt", "Inter-OFL.txt"):
        text = (FONT_DIR / name).read_text()
        assert "SIL OPEN FONT LICENSE Version 1.1" in text


def test_fonts_load_at_the_requested_weight():
    light = inter(40, weight=400)
    heavy = inter(40, weight=800)
    assert light.size == 40
    draw = ImageDraw.Draw(Image.new("L", (10, 10)))
    assert draw.textlength("Manchete", font=heavy) > draw.textlength("Manchete", font=light)


def test_fonts_cover_portuguese_glyphs():
    for font in (fraunces(48, weight=800), inter(48, weight=600)):
        # A missing glyph renders as .notdef, which is the same box for every character.
        boxes = {font.getmask(ch).getbbox() for ch in "çãõéÔ"}
        assert len(boxes) > 1
