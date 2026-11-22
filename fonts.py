"""OFL fonts embedded in the repo, so covers and charts render the same on any machine.

Fraunces is for display text and numbers, Inter for labels. Both are variable
fonts from google/fonts; `weight` picks the instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
FRAUNCES_FILE = FONT_DIR / "Fraunces[SOFT,WONK,opsz,wght].ttf"
INTER_FILE = FONT_DIR / "Inter[opsz,wght].ttf"


@lru_cache(maxsize=64)
def fraunces(size: int, weight: int = 800) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FRAUNCES_FILE), size)
    # Axes: optical size, weight, softness, wonky. Wonky off keeps letters upright.
    font.set_variation_by_axes([min(144, max(9, size)), weight, 0, 0])
    return font


@lru_cache(maxsize=64)
def inter(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(INTER_FILE), size)
    # Axes: optical size, weight.
    font.set_variation_by_axes([min(32, max(14, size)), weight])
    return font
