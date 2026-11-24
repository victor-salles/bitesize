"""Turn an edition's sections into the display strings the cover draws."""

from __future__ import annotations

import re

from ai_locale import (
    epub_label,
    format_count,
    format_decimal,
    format_long_date,
    tema_label,
)
from cover_art import CoverData, CoverDesk, CoverLabels, CoverTeaser, CoverTopic
from edition_data import (
    EditionMeta,
    StoryNumbers,
    format_reading_time,
    reading_minutes,
    short_title,
    topic_mention_counts,
    topic_shares,
)
from gemini import article_relevance
from magazine_layers import lead_for_section, ranked_excluding_hero

TEASERS_ON_COVER = 3
DESKS_ON_COVER = 3


def capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def first_sentence(text: str) -> str:
    text = (text or "").strip()
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return match.group(1) if match else text


def stats_line(sections: dict[str, list[dict]]) -> str:
    """`7 matérias · 21 min`."""
    articles = [art for arts in sections.values() for art in arts or []]
    minutes = sum(reading_minutes(art) for art in articles)
    return f"{format_count(len(articles), 'story', 'stories')} · {format_reading_time(minutes)}"


def percent(share: float) -> str:
    return f"{round(share * 100)}%"


def cover_topics(sections: dict[str, list[dict]]) -> list[CoverTopic]:
    return [
        CoverTopic(
            capitalized(tema_label(s.tema) if s.tema else epub_label("other_topics")),
            s.count,
            percent(s.share),
        )
        for s in topic_shares(topic_mention_counts(sections))
    ]


def build_cover_data(
    sections: dict[str, list[dict]],
    headline: str,
    hero: dict | None,
    hero_category: str | None,
    numbers: StoryNumbers,
    meta: EditionMeta,
) -> CoverData:
    now = meta.now
    category_of = {id(art): cat for cat, arts in sections.items() for art in arts or []}
    hero = hero or {}

    teasers = []
    for _score, category, art in ranked_excluding_hero(sections, hero or None, TEASERS_ON_COVER):
        kicker = " · ".join(p for p in (category, (art.get("source") or "").strip()) if p)
        teasers.append(CoverTeaser(
            number=numbers.label(art),
            kicker=kicker,
            title=(art.get("title") or "").strip(),
            short_title=short_title(art),
            minutes=format_reading_time(reading_minutes(art)),
        ))

    desks = []
    for category, articles in sections.items():
        if not articles or len(desks) == DESKS_ON_COVER:
            continue
        lead = lead_for_section(articles, hero or None) or articles[0]
        desks.append(CoverDesk(category, len(articles), short_title(lead, max_chars=48)))

    mentions = sum(topic_mention_counts(sections).values())
    total = sum(len(arts or []) for arts in sections.values())
    relevance = article_relevance(hero) / 10 if hero else 0.0

    return CoverData(
        headline=headline,
        section=hero_category or category_of.get(id(hero), ""),
        source=(hero.get("source") or "").strip(),
        dek=first_sentence(hero.get("summary") or ""),
        relevance=relevance,
        relevance_label=format_decimal(relevance) if hero else "",
        weekday=epub_label("weekdays")[now.weekday()],
        date_line=format_long_date(now),
        day=f"{now.day:02d}",
        month=epub_label("months")[now.month - 1][:3],
        year=str(now.year),
        stats_line=stats_line(sections),
        edition_label=(
            epub_label("edition_number", number=meta.edition_number) if meta.edition_number else ""
        ),
        teasers=teasers,
        desks=desks,
        topics=cover_topics(sections),
        topics_note=(
            f"{format_count(mentions, 'mention', 'mentions')} · {format_count(total, 'story', 'stories')}"
        ),
        labels=CoverLabels(
            also_inside=epub_label("also_inside"),
            reading=epub_label("reading"),
            topics=epub_label("edition_topics"),
            highlights=epub_label("highlights_today"),
            headline=epub_label("lead_story"),
        ),
    )
