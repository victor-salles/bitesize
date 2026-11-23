"""Small PNGs the EPUB pages use where XHTML on a stock Kindle cannot draw.

No inline SVG and no glyphs a Kindle font may lack (HANDOFF rules 4 and 5):
wavy rules beside section names, relevance squares, the end-of-article mark.
"""

from __future__ import annotations

import io
import re
from functools import lru_cache

from PIL import Image, ImageDraw

WAVE_COLOR = (163, 163, 163)
INK = (17, 17, 17)
# Supersampling factor: draw large, then shrink for smooth lines.
_SUPERSAMPLE = 4

# The two irregular waves from the mockups (Opening.dc.html), in a 125×8 box.
_WAVE_PATHS = {
    "left": "M0 4 Q3 1.5 7 4 Q11 6.8 14 4 Q19 0.6 25 4 Q28 6 31 4 Q34 2.2 38 4 Q44 7.6 50 4 Q53 2 56 4 "
            "Q60 6.2 63 4 Q68 0.8 75 4 Q78 5.8 81 4 Q85 1.8 89 4 Q95 7.4 100 4 Q103 2.6 106 4 Q110 6.4 114 4 "
            "Q119 1 125 4",
    "right": "M0 4 Q5 1 10 4 Q13 6.2 16 4 Q20 1.6 24 4 Q30 7.8 36 4 Q39 2.4 42 4 Q46 6 49 4 Q55 0.4 62 4 "
             "Q65 5.6 68 4 Q72 2 76 4 Q82 7.2 87 4 Q90 2.8 93 4 Q98 6.6 102 4 Q108 1.2 114 4 Q118 6 121 4 "
             "Q123 3 125 4",
}
_WAVE_BOX = (125, 8)
# Output scale: 4 px per mockup px keeps the line crisp at any Kindle font size.
_WAVE_SCALE = 4


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _wave_points(path: str, scale: float) -> list[tuple[float, float]]:
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", path)]
    start, curves = numbers[:2], numbers[2:]
    points = [(start[0] * scale, start[1] * scale)]
    x0, y0 = start
    for i in range(0, len(curves), 4):
        cx, cy, x1, y1 = curves[i : i + 4]
        for step in range(1, 13):
            t = step / 12
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t**2 * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t**2 * y1
            points.append((x * scale, y * scale))
        x0, y0 = x1, y1
    return points


@lru_cache(maxsize=None)
def wave_png(side: str) -> bytes:
    """A light-grey irregular wavy rule on a transparent background."""
    big = _WAVE_SCALE * _SUPERSAMPLE
    width, height = _WAVE_BOX[0] * big, _WAVE_BOX[1] * big
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    ImageDraw.Draw(img).line(_wave_points(_WAVE_PATHS[side], big), fill=WAVE_COLOR + (255,),
                             width=big, joint="curve")
    return _png(img.resize((width // _SUPERSAMPLE, height // _SUPERSAMPLE), Image.LANCZOS))


def score_image_name(score: float) -> str:
    """Image for a 0–10 relevance score: one filled square per point, rounded."""
    return f"images/score-{round(max(0.0, min(10.0, score))):02d}.png"


@lru_cache(maxsize=None)
def score_png(filled: int) -> bytes:
    """Ten squares, *filled* of them black: the mockups' relevance bar."""
    size, gap, border = 28, 8, 4
    img = Image.new("RGBA", (10 * size + 9 * gap, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    for i in range(10):
        left = i * (size + gap)
        draw.rectangle((left, 0, left + size - 1, size - 1), fill=INK if i < filled else (255, 255, 255),
                       outline=INK, width=border)
    return _png(img)


def book_images() -> dict[str, bytes]:
    """Every image the pages may reference, by file name inside the EPUB."""
    images = {f"images/wave-{side}.png": wave_png(side) for side in _WAVE_PATHS}
    images.update({f"images/score-{n:02d}.png": score_png(n) for n in range(11)})
    return images
