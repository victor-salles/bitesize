"""Turn the screenshots into animated WebP carousels for the README.

    python scripts/doc-screenshots/carousel.py [screenshots-dir]

GitHub strips JavaScript from READMEs, so the carousel is an animated image: each
shot holds for a few seconds, then cross-fades into the next.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HOLD_MS = 2800
FADE_FRAMES = 5
FADE_MS = 60

CAROUSELS = {
    "carousel-book.webp": (
        ["book-library-cover.png", "book-cover.png", "book-section.png", "book-index.png", "book-article.png"],
        720,  # output width in px
    ),
    "carousel-dashboard.webp": (
        ["dashboard-settings.png", "dashboard-sources.png", "dashboard-jev.png", "dashboard-kindle.png"],
        1440,
    ),
}


def build(shots: Path, out_name: str, files: list[str], width: int) -> None:
    stills = []
    for name in files:
        im = Image.open(shots / name).convert("RGB")
        stills.append(im.resize((width, round(im.height * width / im.width)), Image.LANCZOS))
    # Pages can differ by a pixel or two; pad every still onto the largest canvas.
    w = max(i.width for i in stills)
    h = max(i.height for i in stills)
    bg = stills[0].getpixel((2, 2))
    canvas = []
    for im in stills:
        c = Image.new("RGB", (w, h), bg)
        c.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
        canvas.append(c)

    frames, durations = [], []
    for i, cur in enumerate(canvas):
        nxt = canvas[(i + 1) % len(canvas)]
        frames.append(cur)
        durations.append(HOLD_MS)
        for step in range(1, FADE_FRAMES + 1):
            frames.append(Image.blend(cur, nxt, step / (FADE_FRAMES + 1)))
            durations.append(FADE_MS)

    out = shots / out_name
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=75, method=6)
    print(out, f"{out.stat().st_size // 1024} KB")


def main() -> None:
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "docs" / "screenshots"
    for out_name, (files, width) in CAROUSELS.items():
        build(shots, out_name, files, width)


if __name__ == "__main__":
    main()
