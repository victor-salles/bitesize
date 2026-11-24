"""Numbers the EPUB shows about an edition: story numbers, reading time, dates, topic counts."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ai_locale import ai_language_code, epub_label

# Average silent reading speed for news prose, in words per minute.
WORDS_PER_MINUTE = 200


@dataclass(frozen=True)
class EditionMeta:
    """What the EPUB needs to know about the edition beyond its articles."""

    now: datetime
    # The reader's Nth edition; None hides "Edição N".
    edition_number: Optional[int] = None
    # Topic mention counts of the previous edition; None hides the "vs. ontem" trend.
    previous_topic_counts: Optional[dict[str, int]] = None
    # cover_art.COVER_STYLES: "numero" (cover B), "jornal" or "jornal-invert" (cover A).
    cover_style: str = "numero"


def word_count(art: dict) -> int:
    text = (art.get("content") or "").strip() or (art.get("summary") or "").strip()
    return len(text.split())


def reading_minutes(art: dict) -> int:
    return max(1, math.ceil(word_count(art) / WORDS_PER_MINUTE))


# Above this many minutes an article is a long read: key points and an outline.
LONG_READ_MINUTES = 8


def is_long(art: dict) -> bool:
    return reading_minutes(art) > LONG_READ_MINUTES


def format_reading_time(minutes: int) -> str:
    return f"{minutes} min"


class StoryNumbers:
    """Continuous story numbers 01–NN across the whole book, in section (spine) order."""

    def __init__(self, sections: dict[str, list[dict]]):
        self._by_id: dict[int, int] = {}
        for articles in sections.values():
            for art in articles or []:
                self._by_id[id(art)] = len(self._by_id) + 1

    @property
    def total(self) -> int:
        return len(self._by_id)

    def number(self, art: dict) -> int:
        return self._by_id[id(art)]

    def label(self, art: dict) -> str:
        return f"{self.number(art):02d}"


def human_published(art: dict) -> str:
    """`8 nov, 06:30` (pt-BR) or `Nov 8, 06:30`; the raw value when there is no timestamp."""
    timestamp = art.get("published_ts")
    if not timestamp:
        return (art.get("published") or "").strip()
    when = datetime.fromtimestamp(timestamp)
    month = epub_label("months")[when.month - 1]
    if ai_language_code() == "pt-BR":
        return f"{when.day} {month[:3]}, {when:%H:%M}"
    return f"{month[:3]} {when.day}, {when:%H:%M}"


def topic_mention_counts(sections: dict[str, list[dict]]) -> dict[str, int]:
    """Every tema of every article counts once: 7 articles can make 14 mentions. Most first."""
    counts = Counter(
        tema for articles in sections.values() for art in articles or [] for tema in art.get("temas") or []
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


# The cover legend and the topics page have room for this many topics.
MAX_TOPICS_SHOWN = 6
# Short titles on cover B fit in about this many characters.
SHORT_TITLE_CHARS = 28


@dataclass(frozen=True)
class TopicShare:
    tema: str  # a tema id, or "" for the merged rest ("outros")
    count: int
    share: float  # 0–1 of all mentions


def topic_shares(counts: dict[str, int], limit: int = MAX_TOPICS_SHOWN) -> list[TopicShare]:
    """The top topics by mentions; past *limit*, the tail merges into one "" entry."""
    total = sum(counts.values())
    if not total:
        return []
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > limit:
        rest = sum(count for _, count in ranked[limit - 1:])
        ranked = ranked[: limit - 1] + [("", rest)]
    return [TopicShare(tema, count, count / total) for tema, count in ranked]


def short_title(art: dict, max_chars: int = SHORT_TITLE_CHARS) -> str:
    """The AI's short title, or the title cut at a word boundary (cache rows from before short titles)."""
    short = (art.get("short_title") or "").strip()
    if short:
        return short
    title = (art.get("title") or "").strip()
    if len(title) <= max_chars:
        return title
    words = title[: max_chars + 1].rsplit(" ", 1)[0].split()
    while len(words) > 1 and len(words[-1].strip(",;:-–—")) <= 3:
        words.pop()
    cut = " ".join(words).rstrip(" ,;:-–—")
    return (cut or title[:max_chars]) + "…"
