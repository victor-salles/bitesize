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


def word_count(art: dict) -> int:
    text = (art.get("content") or "").strip() or (art.get("summary") or "").strip()
    return len(text.split())


def reading_minutes(art: dict) -> int:
    return max(1, math.ceil(word_count(art) / WORDS_PER_MINUTE))


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
