"""Jev questions for one news article. All independent questions go in a single System One call."""

from __future__ import annotations

from typesafe_sdk import Choice, Noul, Score

from tags import TEMAS, TIPOS

READER_NOTES = (
    "The reader is Victor. The digest is a short morning Kindle magazine in Portuguese. "
    "Feeds are already chosen; judge the story itself. "
    "Do not treat `category` as a topic tag — that is only the feed folder."
)

TEMA_NOULS = {f"tema_{t}": t for t in sorted(TEMAS)}

RELEVANCE_CRITERIA = [
    "Filler: no public impact, leftover promo, or a story nobody needs this morning.",
    "Niche: real news, but only a small audience or a follow-up of little consequence.",
    "Solid: belongs in this section of a daily paper.",
    "Important today: national or international impact, or a story most readers will expect.",
    "Lead: the kind of story that would open a newspaper.",
]


def article_state(art: dict) -> dict:
    body = (art.get("content") or art.get("rss_snippet") or "").strip()
    if len(body) > 8000:
        body = body[:8000]
    return {
        "reader": READER_NOTES,
        "title": art.get("title") or "",
        "source": art.get("source") or "",
        "category": art.get("category") or "",
        "url": art.get("link") or art.get("url") or "",
        "body": body,
    }


def news_questions() -> dict:
    questions: dict = {
        "ad": Noul(
            instructions=(
                "Is `title` plus `body` a pure advertisement, advertorial, "
                "sponsored post, or affiliate pitch rather than journalism?"
            ),
            criteria={
                "true": "The piece exists to sell a product, course, or brand. No independent news.",
                "false": "It is reporting, analysis, or opinion journalism, even if a company is mentioned.",
            },
        ),
        "keep": Noul(
            instructions=(
                "Would this story earn a slot in a short Kindle morning edition "
                "for a Brazilian reader who already has too many articles? "
                "Use `title` and `body`. Prefer impact, timeliness, and breadth."
            ),
            criteria={
                "true": "Worth keeping if the book must stay small.",
                "false": "Skip when space is tight: thin, local-only, duplicate-feeling, or low-stakes.",
            },
        ),
        "clickbait": Noul(
            instructions=(
                "Does `title` oversell or withhold what `body` actually delivers?"
            ),
            criteria={
                "true": "Clickbait, curiosity-gap, or a headline that does not match the facts.",
                "false": "The title fairly describes the story.",
            },
        ),
        "press_release": Noul(
            instructions=(
                "Is `body` mostly a company or government press release, lightly rewritten?"
            ),
            criteria={
                "true": "PR copy, product launch fluff, or an official statement with no reporting.",
                "false": "Independent reporting, even if it quotes officials.",
            },
        ),
        "paywall_teaser": Noul(
            instructions=(
                "Is `body` a paywall teaser, subscribe wall, or lede-only fragment, "
                "not a full article?"
            ),
            criteria={
                "true": "Too little body to read; subscribe/paywall language or a snippet echo.",
                "false": "There is enough article text to read on a Kindle.",
            },
        ),
        "relevance": Score(
            instructions=(
                "How important is this story for today's digest, given `title` and `body`? "
                "Compare against a typical morning newspaper, not against other items in a batch."
            ),
            criteria=RELEVANCE_CRITERIA,
        ),
        "tipo": Choice(
            instructions=(
                "Given `body`, is this a short teaser (`resumo`) or enough text to read "
                "(`artigo-completo`)? Ignore `category`."
            ),
            criteria={
                "resumo": "Paywall teaser, lede-only, or too short to read as an article.",
                "artigo-completo": "Enough body to read on a Kindle.",
            },
        ),
    }
    for qid, tema in TEMA_NOULS.items():
        questions[qid] = Noul(
            instructions=(
                f"Should this story be tagged `{tema}` in Portuguese topic tags? "
                "Use `title` and `body`. Multiple tags may be true."
            ),
            criteria={
                "true": f"The story is substantially about {tema}.",
                "false": f"The story is not about {tema}.",
            },
        )
    assert set(TIPOS) == {"resumo", "artigo-completo"}
    assert set(TEMA_NOULS.values()) == set(TEMAS)
    return questions
