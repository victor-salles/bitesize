"""Cover JPEGs for the Kindle library thumbnail, drawn with the embedded fonts.

Two styles (docs/design/kindle-redesign/): "numero" (cover B, the day's number
on a black block) and "jornal" (cover A, a newspaper front page), plus
"jornal-invert" with a black page. Everything arrives as display strings in
CoverData, so this module only draws.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from fonts import fraunces, inter

# 3:4 like the Kindle screen, so the thumbnail has no white side band.
COVER_WIDTH = 1236
COVER_HEIGHT = 1648
# The mockups are drawn at 600 px wide.
_SCALE = COVER_WIDTH / 600

COVER_STYLES = ("numero", "jornal", "jornal-invert")
DEFAULT_COVER_STYLE = "numero"

BRAND = "BiteSIze"

# HANDOFF rule 1: grey tones only.
INK = "#111111"
PAPER = "#ffffff"
GREYS = ("#111111", "#3d3d3d", "#636363", "#8a8a8a", "#b0b0b0", "#d0d0d0")
SECONDARY = "#595959"
LIGHT_RULE = "#cfcfcf"


@dataclass(frozen=True)
class CoverTeaser:
    number: str  # "02"
    kicker: str  # "Ciência · Revista Modelo"
    title: str
    short_title: str  # a few words, for cover B's highlights
    minutes: str  # "3 min"


@dataclass(frozen=True)
class CoverDesk:
    name: str
    count: int
    lead: str


@dataclass(frozen=True)
class CoverTopic:
    name: str
    count: int
    percent: str  # "29%"


@dataclass(frozen=True)
class CoverLabels:
    also_inside: str = "Também nesta edição"
    reading: str = "leitura"
    topics: str = "Temas da edição"
    highlights: str = "Destaques de hoje"
    headline: str = "Manchete"


@dataclass(frozen=True)
class CoverData:
    headline: str
    section: str = ""
    source: str = ""
    dek: str = ""
    relevance: float = 0.0  # 0–10
    relevance_label: str = ""  # "9,2"
    weekday: str = ""
    date_line: str = ""  # "8 de novembro de 2026"
    day: str = ""  # "08"
    month: str = ""  # "nov"
    year: str = ""
    stats_line: str = ""  # "7 matérias · 21 min"
    edition_label: str = ""  # "Edição 312"; empty hides it
    teasers: list[CoverTeaser] = field(default_factory=list)
    desks: list[CoverDesk] = field(default_factory=list)
    topics: list[CoverTopic] = field(default_factory=list)
    topics_note: str = ""  # "14 menções · 7 matérias"
    labels: CoverLabels = field(default_factory=CoverLabels)


@dataclass(frozen=True)
class _Palette:
    background: str
    foreground: str
    soft: str
    muted: str
    rule: str
    shades: tuple[str, ...]


_LIGHT = _Palette(PAPER, INK, "#3d3d3d", SECONDARY, LIGHT_RULE, GREYS)
_DARK = _Palette(INK, PAPER, "#d0d0d0", "#b0b0b0", "#3d3d3d", ("#ffffff",) + GREYS[:0:-1][:5])


def px(mockup_px: float) -> int:
    """A mockup measurement (600 px wide) in cover pixels."""
    return round(mockup_px * _SCALE)


# ── text helpers ─────────────────────────────────────────────────────────────

def text_width(text: str, font: ImageFont.FreeTypeFont, tracking: float = 0) -> float:
    if not text:
        return 0
    return font.getlength(text) + tracking * (len(text) - 1)


def draw_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    baseline: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    tracking: float = 0,
    align: str = "left",
) -> float:
    """Draw *text* on *baseline*, letter-spaced by *tracking* px; returns its width."""
    width = text_width(text, font, tracking)
    if align == "right":
        x -= width
    elif align == "center":
        x -= width / 2
    if not tracking:
        draw.text((x, baseline), text, font=font, fill=fill, anchor="ls")
        return width
    for char in text:
        draw.text((x, baseline), char, font=font, fill=fill, anchor="ls")
        x += font.getlength(char) + tracking
    return width


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in (text or "").split():
        trial = f"{current} {word}".strip()
        if current and font.getlength(trial) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def clamp_lines(lines: list[str], limit: int) -> list[str]:
    if len(lines) <= limit:
        return lines
    kept = lines[:limit]
    kept[-1] = kept[-1].rstrip(" .,;:") + "…"
    return kept


def fit_text(
    text: str, max_width: float, max_lines: int, sizes: tuple[int, ...], make_font
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """The largest size in *sizes* that wraps *text* into *max_lines*; else the smallest, clamped."""
    for size in sizes:
        font = make_font(size)
        lines = wrap(text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = make_font(sizes[-1])
    return font, clamp_lines(wrap(text, font, max_width), max_lines)


def _upper(text: str) -> str:
    return (text or "").upper()


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def draw_relevance_squares(
    draw: ImageDraw.ImageDraw, x: float, top: float, score: float, size: int, gap: int, border: int,
    color: str, empty: str,
) -> float:
    """Ten squares, round(score) of them filled. Returns the width drawn."""
    filled = round(max(0.0, min(10.0, score)))
    for i in range(10):
        left = x + i * (size + gap)
        draw.rectangle(
            (left, top, left + size - 1, top + size - 1),
            fill=color if i < filled else empty, outline=color, width=border,
        )
    return 10 * size + 9 * gap


# ── cover B · número do dia ──────────────────────────────────────────────────

def _render_numero(data: CoverData) -> Image.Image:
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), PAPER)
    draw = ImageDraw.Draw(img)
    pad = px(36)
    right = COVER_WIDTH - pad
    content_width = right - pad
    labels = data.labels

    # Black block: highlights, then the day as a giant numeral.
    block_height = px(330)
    draw.rectangle((0, 0, COVER_WIDTH, block_height), fill=INK)
    label_font = inter(px(12), 600)
    y = px(26) + label_font.size
    draw_text(draw, pad, y, _upper(labels.highlights), label_font, "#b0b0b0", tracking=px(1.4))

    teaser_font = inter(px(14), 700)
    y += px(8) + teaser_font.size
    _draw_highlight_line(draw, pad, y, content_width, [t.short_title for t in data.teasers], teaser_font)

    numeral_font = fraunces(px(220), 900)
    baseline = block_height - px(22)
    draw_text(draw, pad - px(4), baseline, data.day, numeral_font, PAPER, tracking=-px(11))

    weekday_font = inter(px(16), 600)
    year_font = inter(px(16), 500)
    month_font = inter(px(30), 700)
    weekday_base = baseline - px(6)
    draw_text(draw, right, weekday_base, _upper(data.weekday), weekday_font, PAPER, tracking=px(1.9), align="right")
    rule_y = weekday_base - weekday_font.size - px(8)
    rule_width = max(text_width(_upper(data.weekday), weekday_font, px(1.9)), px(70))
    draw.line((right - rule_width, rule_y, right, rule_y), fill="#636363", width=2)
    year_base = rule_y - px(10)
    draw_text(draw, right, year_base, data.year, year_font, "#b0b0b0", align="right")
    month_base = year_base - year_font.size - px(8)
    draw_text(draw, right, month_base, _upper(data.month), month_font, PAPER, tracking=px(1.8), align="right")

    # Footer: stats · logo · edition number.
    footer_base = COVER_HEIGHT - px(28)
    footer_font = inter(px(12), 600)
    logo_font = fraunces(px(22), 800)
    draw_text(draw, pad, footer_base, _upper(data.stats_line), footer_font, SECONDARY, tracking=px(1.2))
    draw_text(draw, COVER_WIDTH / 2, footer_base + px(2), BRAND, logo_font, INK, align="center")
    if data.edition_label:
        draw_text(draw, right, footer_base, _upper(data.edition_label), footer_font, SECONDARY,
                  tracking=px(1.2), align="right")
    footer_rule = footer_base - logo_font.size - px(10)
    draw.line((pad, footer_rule, right, footer_rule), fill=LIGHT_RULE, width=2)

    # Desks: three columns, count left of the name, then a short lead.
    desks_top = _draw_desks(draw, data.desks[:3], pad, content_width, footer_rule - px(14))

    # Headline under the block.
    kicker_font = inter(px(12), 700)
    y = block_height + px(26) + kicker_font.size
    kicker = " · ".join(p for p in (labels.headline, data.section) if p)
    draw_text(draw, pad, y, _upper(kicker), kicker_font, SECONDARY, tracking=px(1.7))
    room = desks_top - px(20) - (y + px(14))
    headline_font, lines = fit_text(
        data.headline, content_width, 4, (px(40), px(36), px(32)), lambda s: fraunces(s, 600)
    )
    line_height = round(headline_font.size * 1.06)
    lines = lines[: max(1, room // line_height)]
    y += px(14)
    for line in lines:
        y += line_height
        draw_text(draw, pad, y - round(headline_font.size * 0.2), line, headline_font, INK, tracking=-px(0.6))
    return img


def _draw_highlight_line(draw, x: float, baseline: float, max_width: float, items: list[str], font) -> None:
    """Short highlights in one or two lines, separated by grey dots."""
    tracking = px(0.8)
    gap = px(10)
    dot_width = text_width("·", font)
    cursor = x
    line = 0
    for i, item in enumerate(i for i in items if i):
        word = _upper(item)
        width = text_width(word, font, tracking)
        if i and cursor + gap + dot_width + gap + width > x + max_width:
            line += 1
            if line == 2:
                return
            cursor = x
            baseline += round(font.size * 1.35)
        elif i:
            cursor += gap
            draw_text(draw, cursor, baseline, "·", font, "#8a8a8a")
            cursor += dot_width + gap
        draw_text(draw, cursor, baseline, word, font, PAPER, tracking=tracking)
        cursor += width


def _draw_desks(draw, desks: list[CoverDesk], left: float, width: float, bottom: float) -> float:
    """Draw the desk columns so they end at *bottom*; returns their top."""
    if not desks:
        return bottom
    gap = px(20)
    column = (width - gap * (len(desks) - 1)) / len(desks)
    count_font = fraunces(px(22), 800)
    name_font = inter(px(13), 700)
    lead_font = fraunces(px(15), 400)
    lead_line = round(lead_font.size * 1.3)
    leads = [clamp_lines(wrap(d.lead, lead_font, column), 3) for d in desks]
    height = px(12) + count_font.size + px(8) + lead_line * max(len(lines) for lines in leads)
    top = bottom - height
    draw.rectangle((left, top, left + width, top + px(3) - 1), fill=INK)
    for i, desk in enumerate(desks):
        x = left + i * (column + gap)
        base = top + px(12) + count_font.size
        count_width = draw_text(draw, x, base, str(desk.count), count_font, INK)
        draw_text(draw, x + count_width + px(8), base, _upper(desk.name), name_font, INK, tracking=px(1.3))
        y = base + px(8)
        for line in leads[i]:
            y += lead_line
            draw_text(draw, x, y - round(lead_font.size * 0.25), line, lead_font, "#3d3d3d")
    return top


# ── cover A · jornal ─────────────────────────────────────────────────────────

def _render_jornal(data: CoverData, palette: _Palette) -> Image.Image:
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), palette.background)
    draw = ImageDraw.Draw(img)
    pad = px(44)
    right = COVER_WIDTH - pad
    content_width = right - pad
    labels = data.labels
    fg, muted = palette.foreground, palette.muted

    # Date line and double rule.
    top_font = inter(px(11), 600)
    y = px(36) + top_font.size
    draw_text(draw, pad, y, _upper(data.weekday), top_font, muted, tracking=px(1.5))
    draw_text(draw, COVER_WIDTH / 2, y, _upper(data.date_line), top_font, muted, tracking=px(1.5), align="center")
    draw_text(draw, right, y, _upper(data.stats_line), top_font, muted, tracking=px(1.5), align="right")
    y += px(10)
    draw.rectangle((pad, y, right, y + px(4) - 1), fill=fg)
    y += px(4) + px(3)
    draw.rectangle((pad, y, right, y + 1), fill=fg)

    # Bottom up: logo between rules, topic legend, topic bar, topic label.
    logo_font = fraunces(px(22), 800)
    logo_base = COVER_HEIGHT - px(24)
    logo_width = draw_text(draw, COVER_WIDTH / 2, logo_base, BRAND, logo_font, fg, align="center")
    rule_y = logo_base - round(logo_font.size * 0.32)
    draw.line((pad, rule_y, COVER_WIDTH / 2 - logo_width / 2 - px(14), rule_y), fill=palette.rule, width=2)
    draw.line((COVER_WIDTH / 2 + logo_width / 2 + px(14), rule_y, right, rule_y), fill=palette.rule, width=2)
    topics_top = _draw_topics(draw, img, data, palette, pad, content_width, logo_base - logo_font.size - px(22))

    # Relevance squares + kicker, headline, dek.
    y += px(40)
    kicker_font = inter(px(12), 700)
    square = px(9)
    draw_relevance_squares(draw, pad, y, data.relevance, square, px(3), max(2, px(1.5)), fg, palette.background)
    base = y + square
    x = pad + 10 * square + 9 * px(3) + px(10)
    x += draw_text(draw, x, base, data.relevance_label, kicker_font, fg, tracking=px(1.7)) + px(10)
    kicker = " · ".join(p for p in (data.section, data.source) if p)
    if kicker:
        draw_text(draw, x, base, _upper(f"· {kicker}"), kicker_font, muted, tracking=px(1.7))
    y = base + px(14)

    headline_font, lines = fit_text(
        data.headline, content_width, 4, (px(52), px(46), px(40)), lambda s: fraunces(s, 600)
    )
    line_height = round(headline_font.size * 1.04)
    for line in lines:
        y += line_height
        draw_text(draw, pad, y - round(headline_font.size * 0.18), line, headline_font, fg, tracking=-px(1))
    dek_font = fraunces(px(19), 400)
    dek_line = round(dek_font.size * 1.4)
    y += px(14)
    for line in clamp_lines(wrap(data.dek, dek_font, content_width), 3):
        y += dek_line
        draw_text(draw, pad, y - round(dek_font.size * 0.25), line, dek_font, palette.soft)

    # "Também nesta edição", as many rows as fit above the topics.
    _draw_teaser_rows(draw, data, palette, pad, content_width, y + px(36), topics_top - px(18))
    return img


def _draw_teaser_rows(draw, data: CoverData, palette: _Palette, left, width, top, bottom) -> None:
    fg, muted = palette.foreground, palette.muted
    head_font = inter(px(12), 700)
    number_font = fraunces(px(26), 800)
    kicker_font = inter(px(11), 600)
    title_font = inter(px(17), 600)
    minutes_font = inter(px(13), 400)
    title_line = round(title_font.size * 1.25)
    number_column = px(44) + px(12)
    minutes_column = px(48) + px(12)
    title_width = width - number_column - minutes_column

    head_base = top + head_font.size
    if head_base + px(8) > bottom:
        return
    draw_text(draw, left, head_base, _upper(data.labels.also_inside), head_font, fg, tracking=px(1.7))
    draw_text(draw, left + width, head_base, _upper(data.labels.reading), head_font, muted,
              tracking=px(1.7), align="right")
    y = head_base + px(6)
    draw.rectangle((left, y, left + width, y + px(2) - 1), fill=fg)
    y += px(2)

    for teaser in data.teasers:
        lines = clamp_lines(wrap(teaser.title, title_font, title_width), 2)
        row = px(9) + kicker_font.size + px(3) + title_line * len(lines) + px(9)
        if y + row > bottom:
            break
        kicker_base = y + px(9) + kicker_font.size
        draw_text(draw, left, kicker_base + px(8), teaser.number, number_font, fg)
        draw_text(draw, left + number_column, kicker_base, _upper(teaser.kicker), kicker_font, muted,
                  tracking=px(1.3))
        line_y = kicker_base + px(3)
        for line in lines:
            line_y += title_line
            draw_text(draw, left + number_column, line_y - round(title_font.size * 0.22), line, title_font, fg)
        draw_text(draw, left + width, kicker_base + px(8), teaser.minutes, minutes_font, muted, align="right")
        y += row
        draw.line((left, y, left + width, y), fill=palette.rule, width=2)


def _draw_topics(draw, img: Image.Image, data: CoverData, palette: _Palette, left, width, bottom) -> float:
    """Segmented topic bar with a three-column legend ending at *bottom*; returns its top."""
    topics = data.topics
    if not topics:
        return bottom
    legend_font = inter(px(12), 600)
    percent_font = inter(px(12), 700)
    row_height = px(12) + px(6)
    columns = 3
    rows = (len(topics) + columns - 1) // columns
    legend_top = bottom - rows * row_height
    column_gap = px(12)
    column_width = (width - column_gap * (columns - 1)) / columns
    swatch = px(10)
    for i, topic in enumerate(topics):
        shade = palette.shades[min(i, len(palette.shades) - 1)]
        x = left + (i % columns) * (column_width + column_gap)
        y = legend_top + (i // columns) * row_height
        draw.rounded_rectangle((x, y, x + swatch, y + swatch), radius=px(2), fill=shade, outline=palette.rule, width=2)
        base = y + swatch
        draw_text(draw, x + swatch + px(7), base, topic.name, legend_font, palette.soft)
        draw_text(draw, x + column_width, base, topic.percent, percent_font, palette.foreground, align="right")

    bar_height = px(12)
    bar_top = legend_top - px(10) - bar_height
    total = sum(t.count for t in topics) or 1
    gap = px(2)
    usable = width - gap * (len(topics) - 1)
    bar = Image.new("RGB", (round(width), bar_height), palette.background)
    bar_draw = ImageDraw.Draw(bar)
    x = 0.0
    for i, topic in enumerate(topics):
        segment = usable * topic.count / total
        shade = palette.shades[min(i, len(palette.shades) - 1)]
        bar_draw.rectangle((round(x), 0, round(x + segment) - 1, bar_height), fill=shade)
        x += segment + gap
    mask = Image.new("L", bar.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bar.size[0] - 1, bar_height - 1), radius=bar_height // 2, fill=255)
    img.paste(bar, (round(left), round(bar_top)), mask)

    label_font = inter(px(11), 700)
    label_base = bar_top - px(8)
    draw_text(draw, left, label_base, _upper(data.labels.topics), label_font, palette.foreground, tracking=px(1.3))
    draw_text(draw, left + width, label_base, _upper(data.topics_note), label_font, palette.muted,
              tracking=px(1.3), align="right")
    return label_base - label_font.size


def render_cover(data: CoverData, style: str = DEFAULT_COVER_STYLE) -> bytes:
    """The cover as JPEG bytes, for the EPUB `cover-image` (Kindle library thumbnail)."""
    if style == "jornal":
        img = _render_jornal(data, _LIGHT)
    elif style == "jornal-invert":
        img = _render_jornal(data, _DARK)
    else:
        img = _render_numero(data)
    return _to_jpeg(img)
