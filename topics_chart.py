"""The topics page chart (TopicsSquares.dc.html) as a PNG: one square per mention, then a table.

Links cannot live inside an image, so the page lists them in HTML below.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from cover_art import GREYS, INK, PAPER, SECONDARY, draw_text, text_width
from fonts import fraunces, inter

CHART_WIDTH = 1200
# The mockup is 536 px wide inside its margins.
_SCALE = CHART_WIDTH / 536
CELL_BORDER = "#8a8a8a"
_TREND_COLORS = {  # kind: (background, text)
    "up": (INK, PAPER),
    "down": (PAPER, INK),
    "same": (PAPER, SECONDARY),
    "new": ("#d0d0d0", INK),
}


def px(mockup_px: float) -> int:
    return round(mockup_px * _SCALE)


@dataclass(frozen=True)
class Trend:
    kind: str  # "up", "down", "same" or "new"
    delta: int


@dataclass(frozen=True)
class ChartRow:
    name: str
    count: int
    percent_short: str  # "29%"
    percent_long: str  # "28,6%"
    numbers: list[str]  # story numbers, one square each
    trend: Optional[Trend]
    note: str
    trend_text: str  # "+2", "igual", "novo"


def _shade(i: int) -> str:
    return GREYS[min(i, len(GREYS) - 1)]


def _squares(draw: ImageDraw.ImageDraw, rows: list[ChartRow], total: int, top: int) -> int:
    """One row of cells, grouped by topic, with each group's share under it. Returns the bottom."""
    group_gap, cell_gap = px(8), px(3)
    usable = CHART_WIDTH - group_gap * (len(rows) - 1)
    cell_height = px(44)
    pill_font = inter(px(10), 800)
    share_font = inter(px(10), 800)
    x = 0.0
    for i, row in enumerate(rows):
        width = usable * row.count / total
        cells = len(row.numbers) or row.count
        cell_width = (width - cell_gap * (cells - 1)) / cells
        if cell_width < px(5):  # too many mentions for squares: one bar for the topic
            cells, cell_width = 1, width
        for c in range(cells):
            left = x + c * (cell_width + cell_gap)
            draw.rectangle((left, top, left + cell_width - 1, top + cell_height - 1), fill=_shade(i),
                           outline=CELL_BORDER, width=2)
            if cells == len(row.numbers) and text_width(row.numbers[c], pill_font) + px(8) <= cell_width:
                label = row.numbers[c]
                pill_w = text_width(label, pill_font) + px(6)
                pill_h = round(pill_font.size * 1.5)
                cx, cy = left + cell_width / 2, top + cell_height / 2
                draw.rounded_rectangle((cx - pill_w / 2, cy - pill_h / 2, cx + pill_w / 2, cy + pill_h / 2),
                                       radius=pill_h // 2, fill=PAPER)
                draw_text(draw, cx, cy + pill_font.size * 0.36, label, pill_font, INK, align="center")
        rule_top = top + cell_height + px(5)
        draw.rectangle((x, rule_top, x + width - 1, rule_top + px(2) - 1), fill=INK)
        if text_width(row.percent_short, share_font) <= width + group_gap:
            draw_text(draw, x + width / 2, rule_top + px(3) + share_font.size, row.percent_short, share_font,
                      INK, align="center")
        x += width + group_gap
    return top + cell_height + px(5) + px(3) + share_font.size + px(4)


def _trend_pill(draw: ImageDraw.ImageDraw, x: float, center: float, trend: Trend, text: str) -> None:
    font = inter(px(10), 800)
    background, color = _TREND_COLORS[trend.kind]
    arrow = px(7) if trend.kind in ("up", "down") else 0
    width = px(7) * 2 + text_width(text, font) + (arrow + px(4) if arrow else 0)
    height = round(font.size * 1.8)
    draw.rounded_rectangle((x, center - height / 2, x + width, center + height / 2), radius=height // 2,
                           fill=background, outline=INK, width=max(2, px(1.5)))
    cursor = x + px(7)
    if arrow:  # a drawn triangle: no ▲▼ glyph the font may lack
        if trend.kind == "up":
            points = [(cursor, center + arrow / 2), (cursor + arrow, center + arrow / 2), (cursor + arrow / 2, center - arrow / 2)]
        else:
            points = [(cursor, center - arrow / 2), (cursor + arrow, center - arrow / 2), (cursor + arrow / 2, center + arrow / 2)]
        draw.polygon(points, fill=color)
        cursor += arrow + px(4)
    draw_text(draw, cursor, center + font.size * 0.36, text, font, color)


def _table(draw: ImageDraw.ImageDraw, rows: list[ChartRow], headers: tuple[str, ...], top: int) -> int:
    _, _, topic, trend_header, count_header, percent_header = headers
    show_trend = any(row.trend for row in rows)
    head_font = inter(px(10), 700)
    name_font = fraunces(px(17), 800)
    note_font = fraunces(px(13), 400)
    number_font = inter(px(13), 600)
    percent_font = inter(px(13), 800)
    columns = {"swatch": 0, "name": px(24), "trend": px(138), "note": px(212) if show_trend else px(138)}
    right = CHART_WIDTH
    count_right = right - px(60)

    base = top + head_font.size
    draw_text(draw, columns["name"], base, topic.upper(), head_font, SECONDARY, tracking=px(1.2))
    if show_trend:
        draw_text(draw, columns["trend"], base, trend_header.upper(), head_font, SECONDARY, tracking=px(1.2))
    draw_text(draw, count_right, base, count_header.upper(), head_font, SECONDARY, tracking=px(1.2), align="right")
    draw_text(draw, right, base, percent_header.upper(), head_font, SECONDARY, tracking=px(1.2), align="right")
    y = base + px(6)
    draw.rectangle((0, y, right, y + px(2) - 1), fill=INK)
    y += px(2)

    row_height = px(33)
    for i, row in enumerate(rows):
        center = y + row_height / 2
        swatch = px(14)
        draw.rounded_rectangle((0, center - swatch / 2, swatch, center + swatch / 2), radius=px(3),
                               fill=_shade(i), outline=CELL_BORDER, width=2)
        draw_text(draw, columns["name"], center + name_font.size * 0.35, row.name, name_font, INK)
        if row.trend:
            _trend_pill(draw, columns["trend"], center, row.trend, row.trend_text)
        if row.note:
            draw_text(draw, columns["note"], center + note_font.size * 0.35, row.note, note_font, "#3d3d3d")
        draw_text(draw, count_right, center + number_font.size * 0.36, str(row.count), number_font, SECONDARY,
                  align="right")
        draw_text(draw, right, center + percent_font.size * 0.36, row.percent_long, percent_font, INK, align="right")
        y += row_height
    return y


def render_topics_chart(rows: list[ChartRow], total: int, headers: tuple[str, ...]) -> bytes:
    """*headers*: (all mentions, legend, topic, vs. last edition, count, percent)."""
    height = px(20) + px(44) + px(30) + px(30) + px(33) * len(rows) + px(10)
    img = Image.new("RGB", (CHART_WIDTH, height), PAPER)
    draw = ImageDraw.Draw(img)
    label_font = inter(px(11), 700)
    base = label_font.size
    draw_text(draw, 0, base, headers[0].upper(), label_font, INK, tracking=px(1.3))
    draw_text(draw, CHART_WIDTH, base, headers[1].upper(), label_font, SECONDARY, tracking=px(1.3), align="right")
    bottom = _squares(draw, rows, max(1, total), base + px(8)) if rows else base
    end = _table(draw, rows, headers, bottom + px(18))
    img = img.crop((0, 0, CHART_WIDTH, min(height, end + px(4))))
    buf = io.BytesIO()
    img.convert("L").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
