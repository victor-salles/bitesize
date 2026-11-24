"""Pages of the redesigned book (docs/design/kindle-redesign/).

Structure only: the reader's Kindle sets body font, size and spacing
(HANDOFF rule 2). Layout uses tables and plain blocks, never flex or grid,
and images for the shapes a Kindle font may lack.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_locale import (
    epub_label,
    format_count,
    format_decimal,
    format_short_date,
    tipo_label,
)
from cover_data import stats_line
from edition_data import EditionMeta, format_reading_time, reading_minutes
from epub_images import score_image_name
from gemini import article_relevance
from magazine_layers import is_same_story
from xhtml import escape, slugify

CONTENTS_FILE = "cover.xhtml"


@dataclass(frozen=True)
class StoryPlace:
    """Where one story sits in the book."""

    number: int  # 1..N across the whole book
    category: str
    index: int  # 1..n within its section
    section_total: int
    href: str

    @property
    def label(self) -> str:
        return f"{self.number:02d}"


class BookLayout:
    """Every story's number and file, in reading (spine) order."""

    def __init__(self, sections: dict[str, list[dict]]):
        self.sections = {cat: arts for cat, arts in sections.items() if arts}
        self._places: dict[int, StoryPlace] = {}
        self.order: list[dict] = []
        for category, articles in self.sections.items():
            for index, art in enumerate(articles, start=1):
                self.order.append(art)
                self._places[id(art)] = StoryPlace(
                    number=len(self.order),
                    category=category,
                    index=index,
                    section_total=len(articles),
                    href=article_file(category, index),
                )

    def place(self, art: dict) -> StoryPlace:
        return self._places[id(art)]


def section_file(category: str) -> str:
    return f"cover_{slugify(category)}.xhtml"


def article_file(category: str, index: int) -> str:
    return f"article_{slugify(category)}_{index:02d}.xhtml"


def relevance_label(art: dict) -> str:
    return format_decimal(article_relevance(art) / 10)


def score_img(art: dict) -> str:
    score = article_relevance(art) / 10
    return (
        f'<img class="score" src="{score_image_name(score)}" '
        f'alt="{escape(epub_label("relevance"))} {escape(relevance_label(art))}"/>'
    )


def tipo_text(art: dict) -> str:
    """`artigo completo` / `resumo`; empty for Inbox and Calendar items, which have no tipo."""
    return tipo_label(art["tipo"]).lower() if art.get("tipo") else ""


def minutes(art: dict) -> str:
    return format_reading_time(reading_minutes(art))


def running_head(left: str, right: str) -> str:
    return (
        '<table class="running-head"><tr>'
        f'<td class="running-left">{escape(left)}</td>'
        f'<td class="running-right">{escape(right)}</td>'
        "</tr></table>"
    )


def wavy_heading(name: str, tag: str = "h2", css_class: str = "desk-head") -> str:
    """A centred name between two light-grey wavy rules (PNG, so no SVG)."""
    return (
        f'<{tag} class="{css_class}">'
        '<img class="wave" src="images/wave-left.png" alt=""/>'
        f'<span class="wave-name">{escape(name)}</span>'
        '<img class="wave" src="images/wave-right.png" alt=""/>'
        f"</{tag}>"
    )


# ── contents (Opening.dc.html) ───────────────────────────────────────────────

def _lead_entry(art: dict, category: str, layout: BookLayout) -> str:
    place = layout.place(art)
    kicker = " · ".join(p for p in (epub_label("lead_story"), category, (art.get("source") or "").strip()) if p)
    meta = " · ".join(p for p in (relevance_label(art), minutes(art), tipo_text(art)) if p)
    dek = (art.get("summary") or "").strip()
    dek_html = f'<p class="toc-dek">{escape(dek)}</p>' if dek else ""
    return (
        '<table class="toc-row toc-lead"><tr>'
        f'<td class="toc-num toc-num-lead">{place.label}</td>'
        '<td class="toc-main">'
        f'<p class="kicker">{escape(kicker)}</p>'
        f'<p class="toc-lead-title"><a href="{place.href}">{escape(art.get("title", ""))}</a></p>'
        f"{dek_html}"
        f'<p class="toc-meta">{score_img(art)} {escape(meta)}</p>'
        "</td></tr></table>"
    )


def _entry(art: dict, layout: BookLayout) -> str:
    place = layout.place(art)
    source = (art.get("source") or "").strip()
    relevance = f'{epub_label("relevance").lower()} {relevance_label(art)}'
    meta = " · ".join(p for p in (source, relevance) if p)
    return (
        '<table class="toc-row"><tr>'
        f'<td class="toc-num">{place.label}</td>'
        '<td class="toc-main">'
        f'<p class="toc-title"><a href="{place.href}">{escape(art.get("title", ""))}</a></p>'
        f'<p class="toc-meta">{escape(meta)}</p>'
        "</td>"
        f'<td class="toc-min">{escape(minutes(art))}</td>'
        "</tr></table>"
    )


def contents_body(
    layout: BookLayout, hero: dict | None, hero_category: str | None, meta: EditionMeta
) -> str:
    """The opening contents: the headline first, then every section's stories."""
    head = running_head("BiteSIze", f"{format_short_date(meta.now)} · {stats_line(layout.sections)}")
    parts = [head, f'<h1 class="opening-title">{escape(epub_label("edition_overview"))}</h1>']
    if hero is not None:
        parts.append(_lead_entry(hero, hero_category or layout.place(hero).category, layout))

    for category, articles in layout.sections.items():
        others = [art for art in articles if not (hero is not None and is_same_story(art, hero))]
        count = format_count(len(articles), "story", "stories")
        if len(others) < len(articles):
            count += f' · {epub_label("includes_lead_story")}'
        parts.append('<div class="toc-desk">')
        parts.append(wavy_heading(category))
        parts.append(f'<p class="desk-count">{escape(count)}</p>')
        parts.extend(_entry(art, layout) for art in others)
        parts.append("</div>")
    return "".join(parts)


# ── section opener (Section.dc.html) ─────────────────────────────────────────

def nav_bar(left: tuple[str, str] | None, center: tuple[str, str] | None, right: tuple[str, str] | None) -> str:
    """← left · center · right →, each an (href, label) or None."""
    cells = []
    for position, link in (("left", left), ("center", center), ("right", right)):
        if link is None:
            cells.append(f'<td class="nav-{position}"></td>')
            continue
        href, label = link
        text = {"left": f"&#8592; {escape(label)}", "center": escape(label), "right": f"{escape(label)} &#8594;"}
        cells.append(f'<td class="nav-{position}"><a href="{href}">{text[position]}</a></td>')
    return f'<table class="page-nav"><tr>{"".join(cells)}</tr></table>'


def section_body(category: str, layout: BookLayout) -> str:
    articles = layout.sections[category]
    categories = list(layout.sections)
    position = categories.index(category)
    total_minutes = sum(reading_minutes(art) for art in articles)
    sources = list(dict.fromkeys((art.get("source") or "").strip() for art in articles if art.get("source")))

    parts = [
        '<div class="section-band">',
        running_head(
            epub_label("section_of", index=position + 1, total=len(categories)),
            f"{format_count(len(articles), 'story', 'stories')} · {format_reading_time(total_minutes)}",
        ),
        f'<h1 class="section-name">{escape(category)}</h1>',
        f'<p class="section-sources">{escape(" · ".join(sources))}</p>' if sources else "",
        "</div>",
    ]

    lead, others = articles[0], articles[1:]
    place = layout.place(lead)
    kicker = " · ".join(p for p in (place.label, epub_label("section_lead"), (lead.get("source") or "").strip()) if p)
    meta = " · ".join(p for p in (relevance_label(lead), minutes(lead), tipo_text(lead)) if p)
    dek = (lead.get("summary") or "").strip()
    parts.append(
        '<div class="section-lead">'
        f'<p class="kicker">{escape(kicker)}</p>'
        f'<p class="section-lead-title"><a href="{place.href}">{escape(lead.get("title", ""))}</a></p>'
        + (f'<p class="section-dek">{escape(dek)}</p>' if dek else "")
        + f'<p class="toc-meta">{score_img(lead)} {escape(meta)}</p>'
        "</div>"
    )
    for art in others:
        place = layout.place(art)
        dek = (art.get("summary") or "").strip()
        relevance = f'{epub_label("relevance")} {relevance_label(art)}'
        meta = " · ".join(p for p in (relevance, minutes(art), tipo_text(art)) if p)
        parts.append(
            '<table class="section-row"><tr>'
            f'<td class="section-num">{place.label}</td>'
            '<td class="toc-main">'
            f'<p class="kicker">{escape((art.get("source") or "").strip())}</p>'
            f'<p class="section-title"><a href="{place.href}">{escape(art.get("title", ""))}</a></p>'
            + (f'<p class="section-dek">{escape(dek)}</p>' if dek else "")
            + f'<p class="toc-meta">{escape(meta)}</p>'
            "</td></tr></table>"
        )

    next_category = categories[position + 1] if position + 1 < len(categories) else None
    parts.append(nav_bar(
        (CONTENTS_FILE, epub_label("contents_short")),
        (layout.place(lead).href, epub_label("start_reading")),
        (section_file(next_category), next_category) if next_category else None,
    ))
    return "".join(parts)


PAGES_CSS = """
/* ── Redesign (docs/design/kindle-redesign): structure only, greys only ──── */
.running-head { width: 100%; border-collapse: collapse; margin: 0 0 0.4em 0; }
.running-head td {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.62em; font-weight: bold; letter-spacing: 0.14em;
  text-transform: uppercase; color: #595959; padding: 0;
}
.running-head td.running-right { text-align: right; }
.kicker {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.62em; font-weight: bold; letter-spacing: 0.12em;
  text-transform: uppercase; color: #595959; margin: 0 0 0.3em 0; text-align: left;
}
img.score { height: 0.55em; width: auto; vertical-align: baseline; }
img.wave { width: 5.5em; height: auto; vertical-align: middle; }

h1.opening-title {
  font-size: 1.9em; line-height: 1.1;
  border-bottom: 0.1em solid #111111; padding-bottom: 0.25em; margin: 0.2em 0 0 0;
}
table.toc-row { width: 100%; border-collapse: collapse; }
table.toc-row td { vertical-align: top; padding: 0.5em 0 0.15em 0; }
td.toc-num {
  width: 2.6em;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: bold; color: #3d3d3d;
}
td.toc-num-lead { font-size: 1.7em; color: #111111; line-height: 1; width: 1.6em; }
td.toc-min {
  width: 3.4em; text-align: right;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.62em; font-weight: bold; color: #595959; padding-top: 1.2em;
}
table.toc-lead td { padding-top: 0.9em; }
.toc-lead-title { font-size: 1.25em; font-weight: bold; line-height: 1.2; margin: 0 0 0.25em 0; text-align: left; }
.toc-title { font-weight: bold; line-height: 1.25; margin: 0; text-align: left; }
.toc-lead-title a, .toc-title a { color: #111111; text-decoration: none; }
.toc-dek { font-size: 0.85em; color: #3d3d3d; line-height: 1.4; margin: 0 0 0.3em 0; text-align: left; }
.toc-meta {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.62em; color: #595959; margin: 0.15em 0 0 0; text-align: left;
}
.toc-desk { margin-top: 1.1em; }
h2.desk-head {
  text-align: center; font-family: Georgia, "Bookerly", serif;
  font-size: 1.45em; font-weight: bold; letter-spacing: -0.01em; margin: 0; line-height: 1.1;
}
h2.desk-head .wave-name { padding: 0 0.45em; }
div.section-band { background-color: #111111; color: #ffffff; padding: 0.9em 0.9em 0.8em 0.9em; margin: 0; }
div.section-band .running-head td { color: #d0d0d0; }
h1.section-name {
  font-family: Georgia, "Bookerly", serif; font-size: 2.6em; line-height: 1; letter-spacing: -0.02em;
  border: none; padding: 0; margin: 0.35em 0 0.2em 0; color: #ffffff;
}
.section-sources {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.62em; font-weight: bold;
  letter-spacing: 0.1em; text-transform: uppercase; color: #d0d0d0; margin: 0; text-align: left;
}
div.section-lead { padding: 0.9em 0 0.8em 0; border-bottom: 0.12em solid #111111; }
.section-lead-title { font-size: 1.4em; font-weight: bold; line-height: 1.15; margin: 0 0 0.3em 0; text-align: left; }
.section-title { font-size: 1.05em; font-weight: bold; line-height: 1.25; margin: 0 0 0.2em 0; text-align: left; }
.section-lead-title a, .section-title a { color: #111111; text-decoration: none; }
.section-dek { font-size: 0.9em; color: #3d3d3d; line-height: 1.45; margin: 0 0 0.25em 0; text-align: left; }
table.section-row { width: 100%; border-collapse: collapse; border-bottom: 0.06em solid #d0d0d0; }
table.section-row td { vertical-align: top; padding: 0.75em 0; }
td.section-num {
  width: 2.2em; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-weight: bold; font-size: 1.05em; line-height: 1.2;
}
.desk-count {
  text-align: center;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.62em; font-weight: bold; letter-spacing: 0.12em;
  text-transform: uppercase; color: #595959; margin: 0.15em 0 0.1em 0;
}
table.page-nav { width: 100%; border-collapse: collapse; border-top: 0.12em solid #111111; margin-top: 1.2em; }
table.page-nav td {
  padding: 0.7em 0; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.7em;
  font-weight: bold; letter-spacing: 0.1em; text-transform: uppercase;
}
table.page-nav td.nav-center { text-align: center; }
table.page-nav td.nav-right { text-align: right; }
"""
