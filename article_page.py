"""Article pages (Article, ArticleLong and ArticleLongEnd mockups)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ai_locale import ai_language_code, epub_label, tema_label, tipo_label
from config import get_settings
from edition_data import WORDS_PER_MINUTE, format_reading_time, human_published, is_long, word_count
from epub_pages import (
    CONTENTS_FILE,
    BookLayout,
    minutes,
    nav_bar,
    relevance_label,
    running_head,
    score_img,
    section_file,
)
from xhtml import escape, safe_href

# A subheading is a short line without closing punctuation.
_HEADING_MAX_CHARS = 80
_HEADING_MAX_WORDS = 10
_SENTENCE_END = tuple('.!?:;,…"”\')')


@dataclass(frozen=True)
class Block:
    text: str
    heading: bool = False
    anchor: str = ""


def _is_heading(line: str, following: str | None) -> bool:
    return (
        following is not None
        and len(line) <= _HEADING_MAX_CHARS
        and len(line.split()) <= _HEADING_MAX_WORDS
        and not line.endswith(_SENTENCE_END)
        and len(following) > 2 * len(line)
    )


def article_blocks(content: str) -> list[Block]:
    """Paragraphs and subheadings. The text arrives as plain lines (trafilatura), so a
    subheading is told apart by shape: a short unpunctuated line before a longer one."""
    lines = [line.strip() for line in (content or "").split("\n") if line.strip()]
    blocks: list[Block] = []
    for i, line in enumerate(lines):
        following = lines[i + 1] if i + 1 < len(lines) else None
        if i > 0 and _is_heading(line, following):
            blocks.append(Block(line, heading=True, anchor=f"parte-{sum(b.heading for b in blocks) + 1}"))
        else:
            blocks.append(Block(line))
    return blocks


def _format_words(count: int) -> str:
    separator = "." if ai_language_code() == "pt-BR" else ","
    return f"{count:,}".replace(",", separator) + f" {epub_label('words')}"


def _tag_pills(art: dict) -> str:
    pills = []
    if art.get("tipo"):
        pills.append(f'<span class="pill pill-dark">{escape(tipo_label(art["tipo"]))}</span>')
    pills.extend(f'<span class="pill">{escape(tema_label(t))}</span>' for t in art.get("temas") or [])
    return f'<p class="pills">{" ".join(pills)}</p>' if pills else ""


def _key_points(art: dict) -> list[str]:
    points = art.get("key_points") or []
    return [p for p in points if isinstance(p, str) and p.strip()][:3]


def summary_block(art: dict) -> str:
    """Resumo (or Pontos-chave on a long read) between a thick and a thin rule, with the tags."""
    summary = (art.get("summary") or "").strip()
    points = _key_points(art) if is_long(art) else []
    pills = _tag_pills(art)
    if not summary and not points:
        return f'<div class="summary-box">{pills}</div>' if pills else ""

    label = epub_label("key_points") if points else epub_label("summary")
    head = (
        '<table class="summary-head"><tr>'
        f'<td class="summary-name">{escape(label)}</td>'
        f'<td class="summary-score">{score_img(art)} {escape(epub_label("relevance"))} {escape(relevance_label(art))}</td>'
        "</tr></table>"
    )
    if points:
        rows = "".join(
            f'<tr><td class="point-num">{i}</td><td class="point-text">{escape(point)}</td></tr>'
            for i, point in enumerate(points, start=1)
        )
        content = f'<table class="key-points">{rows}</table>'
    else:
        content = f'<p class="summary-text">{escape(summary)}</p>'
    return f'<div class="summary-box">{head}{content}{pills}</div>'


def outline_block(blocks: list[Block]) -> str:
    """"Neste artigo": links to the subheadings, with each part's reading time."""
    parts: list[tuple[Block, int]] = []
    for block in blocks:
        if block.heading:
            parts.append((block, 0))
        elif parts:
            heading, words = parts[-1]
            parts[-1] = (heading, words + len(block.text.split()))
    if not parts:
        return ""
    rows = "".join(
        f'<tr><td><a href="#{heading.anchor}">{escape(heading.text)}</a></td>'
        f'<td class="outline-min">{format_reading_time(max(1, -(-words // WORDS_PER_MINUTE)))}</td></tr>'
        for heading, words in parts
    )
    return (
        '<div class="outline">'
        f'<p class="kicker">{escape(epub_label("in_this_article"))}</p>'
        f'<table class="outline-list">{rows}</table>'
        "</div>"
    )


def body_block(blocks: list[Block]) -> str:
    """Paragraphs with a drop cap on the first one, numbered subheadings and the end mark."""
    total = sum(block.heading for block in blocks)
    last_paragraph = max((i for i, block in enumerate(blocks) if not block.heading), default=-1)
    parts, seen_paragraph, heading_number = [], False, 0
    for i, block in enumerate(blocks):
        if block.heading:
            heading_number += 1
            parts.append(
                f'<p class="part-of">{escape(epub_label("part_of", index=heading_number, total=total))}</p>'
                f'<h2 class="subhead" id="{block.anchor}">{escape(block.text)}</h2>'
            )
            continue
        css = ' class="lede"' if not seen_paragraph else ""
        seen_paragraph = True
        end = ' <img class="end-mark" src="images/end-mark.png" alt=""/>' if i == last_paragraph else ""
        parts.append(f"<p{css}>{escape(block.text)}{end}</p>")
    return f'<div class="article-body">{"".join(parts)}</div>'


def _source_line(art: dict) -> str:
    href = safe_href(art.get("url", ""))
    if not href:
        return ""
    parsed = urlparse(art["url"].strip())
    shown = (parsed.netloc.removeprefix("www.") + parsed.path).rstrip("/")
    return f'<p class="source-line">{escape(epub_label("original_source"))}: <a href="{href}">{escape(shown)}</a></p>'


def article_body(art: dict, layout: BookLayout) -> str:
    place = layout.place(art)
    long_read = is_long(art)
    content = (art.get("content") or "").strip()
    summary = (art.get("summary") or "").strip()
    show_body = len(content) >= get_settings().min_body_chars or (content and not summary)
    blocks = article_blocks(content) if show_body else []

    right = (
        f"{epub_label('long_read')} · {minutes(art)}" if long_read
        else epub_label("in_this_section", index=place.index, total=place.section_total)
    )
    byline = [f'<span class="byline-source">{escape((art.get("source") or "").strip())}</span>']
    byline += [escape(p) for p in (human_published(art), _format_words(word_count(art)) if long_read else minutes(art)) if p]
    parts = [
        f'<div id="top">{running_head(f"{place.label} · {place.category}", right)}</div>',
        f'<h1 class="story-title">{escape(art.get("title", ""))}</h1>',
        f'<p class="byline">{" · ".join(byline)}</p>',
        summary_block(art),
    ]
    if long_read:
        parts.append(outline_block(blocks))
    if blocks:
        parts.append(body_block(blocks))
    parts.append(_source_line(art))

    following = layout.order[place.number] if place.number < len(layout.order) else None
    if long_read:
        parts.append(f'<p class="back-to-top"><a href="#top">{escape(epub_label("back_to_top"))}</a></p>')
        if following is not None:
            next_place = layout.place(following)
            kicker = " · ".join((epub_label("up_next"), next_place.label, next_place.category, minutes(following)))
            parts.append(
                '<div class="up-next">'
                f'<p class="kicker">{escape(kicker)}</p>'
                f'<p class="up-next-title"><a href="{next_place.href}">{escape(following.get("title", ""))}</a></p>'
                "</div>"
            )
    parts.append(nav_bar(
        (section_file(place.category), place.category),
        (CONTENTS_FILE, epub_label("contents_short")),
        (layout.place(following).href, f'{layout.place(following).label} {epub_label("next")}') if following else None,
    ))
    return "".join(parts)


ARTICLE_CSS = """
.running-head + h1, h1.story-title {
  font-size: 1.7em; line-height: 1.12; border: none; padding: 0; margin: 0.6em 0 0 0;
}
div#top .running-head { border-bottom: 0.06em solid #d0d0d0; padding-bottom: 0.3em; }
.byline {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.75em; color: #3d3d3d;
  margin: 0.5em 0 0 0; text-align: left;
}
.byline-source { font-weight: bold; color: #111111; }
div.summary-box {
  border-top: 0.18em solid #111111; border-bottom: 0.06em solid #111111;
  padding: 0.6em 0 0.7em 0; margin: 0.9em 0 0 0;
}
table.summary-head { width: 100%; border-collapse: collapse; }
table.summary-head td {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.62em; font-weight: bold;
  letter-spacing: 0.12em; text-transform: uppercase; padding: 0;
}
td.summary-score { text-align: right; color: #3d3d3d; }
.summary-text { margin: 0.4em 0 0 0; text-align: left; }
table.key-points { border-collapse: collapse; margin-top: 0.4em; }
td.point-num {
  width: 1.4em; vertical-align: top; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.7em; font-weight: bold; padding-top: 0.35em;
}
td.point-text { padding: 0.1em 0; }
p.pills { margin: 0.5em 0 0 0; line-height: 2; text-align: left; }
span.pill {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.6em; font-weight: bold;
  letter-spacing: 0.06em; text-transform: uppercase; border: 0.08em solid #636363; padding: 0.2em 0.45em;
}
span.pill-dark { background-color: #111111; color: #ffffff; border-color: #111111; }
div.outline { margin: 0.9em 0 0 0; }
table.outline-list { width: 100%; border-collapse: collapse; }
table.outline-list td {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.8em; font-weight: bold;
  border-bottom: 0.06em dotted #8a8a8a; padding: 0.35em 0;
}
table.outline-list a { color: #111111; }
td.outline-min { text-align: right; font-weight: normal; color: #595959; width: 4em; }
.article-body p.lede::first-letter {
  font-size: 3.1em; float: left; line-height: 0.85; padding: 0.05em 0.1em 0 0; font-weight: bold;
}
p.part-of {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.62em; font-weight: bold;
  letter-spacing: 0.12em; text-transform: uppercase; color: #595959; margin: 1.4em 0 0.1em 0;
}
h2.subhead { font-size: 1.3em; border-bottom: 0.1em solid #111111; padding-bottom: 0.2em; margin: 0 0 0.6em 0; }
img.end-mark { height: 0.6em; width: auto; vertical-align: baseline; }
.source-line {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.7em; color: #595959;
  border-top: 0.06em solid #d0d0d0; padding-top: 0.6em; margin-top: 1.2em; text-align: left;
}
.source-line a { color: #595959; }
.back-to-top { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.75em; font-weight: bold; }
div.up-next { border: 0.12em solid #111111; padding: 0.7em 0.8em; margin-top: 1.2em; }
.up-next-title { font-weight: bold; font-size: 1.1em; line-height: 1.25; margin: 0; text-align: left; }
.up-next-title a { color: #111111; }
"""
