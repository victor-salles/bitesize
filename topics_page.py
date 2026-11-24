"""The "Temas da edição" page (TopicsSquares.dc.html), right after the contents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_locale import epub_label, format_count, format_decimal, format_short_date, tema_label
from cover_data import capitalized
from edition_data import EditionMeta, topic_mention_counts, topic_shares
from epub_pages import CONTENTS_FILE, BookLayout, running_head, section_file, wavy_heading
from topics_chart import ChartRow, Trend, render_topics_chart
from xhtml import escape

__all__ = ["Trend", "TopicsData", "TopicRow", "topics_data", "topics_body", "TOPICS_FILE", "TOPICS_CHART_FILE"]

TOPICS_FILE = "topics.xhtml"
TOPICS_CHART_FILE = "images/topics.png"


@dataclass(frozen=True)
class TopicRow:
    temas: tuple[str, ...]  # one tema, or the merged tail ("outros")
    name: str
    count: int
    share: float
    story_numbers: list[str]  # one entry per mention, in book order
    story_hrefs: list[str]
    trend: Optional[Trend]
    note: str

    @property
    def percent_short(self) -> str:
        return f"{round(self.share * 100)}%"

    @property
    def percent_long(self) -> str:
        return f"{format_decimal(self.share * 100)}%"

    @property
    def trend_text(self) -> str:
        if self.trend is None:
            return ""
        if self.trend.kind == "new":
            return epub_label("trend_new")
        if self.trend.kind == "same":
            return epub_label("trend_same")
        return f"+{self.trend.delta}" if self.trend.delta > 0 else f"−{-self.trend.delta}"


@dataclass(frozen=True)
class TopicsData:
    rows: list[TopicRow]
    total: int
    topic_of_day: Optional[TopicRow]
    most_crossed_number: str
    most_crossed_topics: int
    novelty: Optional[TopicRow]


def _trend(temas: tuple[str, ...], count: int, previous: Optional[dict[str, int]]) -> Optional[Trend]:
    if previous is None:
        return None
    before = sum(previous.get(tema, 0) for tema in temas)
    if before == 0:
        return Trend("new", 0)
    delta = count - before
    return Trend("up" if delta > 0 else "down" if delta < 0 else "same", delta)


def _tie_notes(rows: list[tuple[tuple[str, ...], str, int]]) -> dict[str, str]:
    notes = {}
    for _, name, count in rows:
        tied = [other for _, other, other_count in rows if other != name and other_count == count]
        notes[name] = epub_label("tied_with", name=tied[0]) if len(tied) == 1 else ""
    return notes


def topics_data(layout: BookLayout, previous: Optional[dict[str, int]]) -> TopicsData:
    counts = topic_mention_counts(layout.sections)
    shares = topic_shares(counts)
    shown = {s.tema for s in shares if s.tema}
    named = []
    for s in shares:
        temas = (s.tema,) if s.tema else tuple(t for t in counts if t not in shown)
        name = capitalized(tema_label(s.tema) if s.tema else epub_label("other_topics"))
        named.append((temas, name, s))
    notes = _tie_notes([(temas, name, s.count) for temas, name, s in named])

    rows = []
    for temas, name, s in named:
        stories = [art for art in layout.order for tema in art.get("temas") or [] if tema in temas]
        rows.append(TopicRow(
            temas=temas,
            name=name,
            count=s.count,
            share=s.share,
            story_numbers=[layout.place(art).label for art in stories],
            story_hrefs=[layout.place(art).href for art in stories],
            trend=_trend(temas, s.count, previous),
            note=notes[name],
        ))

    crossed = max(layout.order, key=lambda art: len(art.get("temas") or []), default=None)
    novelty = next((row for row in rows if row.trend and row.trend.kind == "new" and len(row.temas) == 1), None)
    return TopicsData(
        rows=rows,
        total=sum(counts.values()),
        topic_of_day=rows[0] if rows else None,
        most_crossed_number=layout.place(crossed).label if crossed else "",
        most_crossed_topics=len(crossed.get("temas") or []) if crossed else 0,
        novelty=novelty if previous is not None else None,
    )


def topics_chart_png(data: TopicsData) -> bytes:
    rows = [
        ChartRow(r.name, r.count, r.percent_short, r.percent_long, r.story_numbers, r.trend, r.note, r.trend_text)
        for r in data.rows
    ]
    headers = (
        epub_label("all_mentions"),
        f"{data.total} · {epub_label('square_legend')}",
        epub_label("topic_header"),
        epub_label("vs_last_edition"),
        epub_label("count_header"),
        "%",
    )
    return render_topics_chart(rows, data.total, headers)


def _card(label: str, value: str, note: str, css: str) -> str:
    return (
        f'<td class="topic-card {css}">'
        f'<p class="card-label">{escape(label)}</p>'
        f'<p class="card-value">{escape(value)}</p>'
        f'<p class="card-note">{escape(note)}</p>'
        "</td>"
    )


def topics_body(data: TopicsData, layout: BookLayout, meta: EditionMeta) -> str:
    stats = (
        f"{format_short_date(meta.now)} · {format_count(len(layout.order), 'story', 'stories')}"
        f" · {format_count(len([t for r in data.rows for t in r.temas]), 'topic', 'topics')}"
    )
    parts = [running_head("BiteSIze", stats), wavy_heading(epub_label("edition_topics"), "h1", "topics-head")]

    cards = []
    if data.topic_of_day:
        cards.append(_card(epub_label("topic_of_day"), data.topic_of_day.name,
                           epub_label("share_of_mentions", percent=data.topic_of_day.percent_short), "card-dark"))
    if data.most_crossed_topics > 1:
        cards.append(_card(epub_label("most_crossed"), epub_label("story_number", number=data.most_crossed_number),
                           epub_label("in_topics", count=data.most_crossed_topics), "card-light"))
    if data.novelty:
        cards.append(_card(epub_label("novelty"), data.novelty.name, epub_label("not_last_edition"), "card-grey"))
    if cards:
        parts.append(f'<table class="topic-cards"><tr>{"".join(cards)}</tr></table>')

    parts.append(
        f'<p class="topics-chart"><img src="{TOPICS_CHART_FILE}" '
        f'alt="{escape(epub_label("all_mentions"))}: {data.total}"/></p>'
    )

    parts.append(f'<h2 class="where-head">{escape(epub_label("where_to_read"))}</h2>')
    for row in data.rows:
        links = " ".join(
            f'<a class="story-pill" href="{href}">{number}</a>'
            for number, href in dict(zip(row.story_numbers, row.story_hrefs)).items()
        )
        parts.append(f'<p class="where-row"><span class="where-name">{escape(row.name)}</span> {links}</p>')

    first_section = next(iter(layout.sections), None)
    nav = [f'<td><a href="{CONTENTS_FILE}">&#8592; {escape(epub_label("contents_short"))}</a></td>']
    if first_section:
        nav.append(f'<td class="nav-right"><a href="{section_file(first_section)}">{escape(first_section)} &#8594;</a></td>')
    parts.append(f'<table class="page-nav"><tr>{"".join(nav)}</tr></table>')
    return "".join(parts)


TOPICS_CSS = """
h1.topics-head {
  text-align: center; font-family: Georgia, "Bookerly", serif;
  font-size: 1.6em; border: none; padding: 0; margin: 0.3em 0 0.6em 0; line-height: 1.1;
}
h1.topics-head .wave-name { padding: 0 0.4em; }
table.topic-cards { width: 100%; border-collapse: separate; border-spacing: 0.4em 0; margin: 0 -0.4em; }
td.topic-card { width: 33%; vertical-align: top; border: 0.12em solid #111111; padding: 0.45em 0.55em; }
td.card-dark { background-color: #111111; color: #ffffff; }
td.card-grey { background-color: #d0d0d0; }
.card-label {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.55em; font-weight: bold;
  letter-spacing: 0.12em; text-transform: uppercase; margin: 0; text-align: left;
}
.card-value { font-family: Georgia, "Bookerly", serif; font-weight: bold; font-size: 1.1em; margin: 0.1em 0; line-height: 1.1; text-align: left; }
.card-note { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.6em; margin: 0; text-align: left; }
p.topics-chart { margin: 1.2em 0 0.6em 0; text-align: center; }
p.topics-chart img { width: 100%; height: auto; }
h2.where-head {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.62em; letter-spacing: 0.12em;
  text-transform: uppercase; color: #595959; margin: 0.8em 0 0.3em 0;
}
p.where-row { margin: 0 0 0.35em 0; text-align: left; line-height: 1.9; }
.where-name { font-weight: bold; padding-right: 0.3em; }
a.story-pill {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.7em; font-weight: bold;
  border: 0.1em solid #111111; padding: 0.1em 0.45em; margin-right: 0.2em; color: #111111;
}
table.page-nav { width: 100%; border-collapse: collapse; border-top: 0.12em solid #111111; margin-top: 1.2em; }
table.page-nav td {
  padding: 0.7em 0; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.7em;
  font-weight: bold; letter-spacing: 0.1em; text-transform: uppercase;
}
table.page-nav td.nav-center { text-align: center; }
table.page-nav td.nav-right { text-align: right; }
"""
