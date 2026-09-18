"""Jev questions for one news article. All independent questions go in a single System One call."""

from __future__ import annotations

from typesafe_sdk import Choice, Noul

from tags import TIPOS

SNIPPET_CHARS = 480


def tema_nouls() -> dict[str, str]:
    from themes import list_themes

    return {f"tema_{t['id']}": t["id"] for t in list_themes() if t["enabled"]}


def article_state(art: dict) -> dict:
    raw = (art.get("content") or art.get("rss_snippet") or "").strip()
    snippet = raw[:SNIPPET_CHARS]
    if len(raw) > SNIPPET_CHARS:
        cut = snippet.rfind(" ")
        if cut >= SNIPPET_CHARS // 2:
            snippet = snippet[:cut]
    return {
        "title": art.get("title") or "",
        "source": art.get("source") or "",
        "snippet": snippet.strip(),
        "body_chars": len(raw),
    }


def news_questions() -> dict:
    tema_map = tema_nouls()
    questions: dict = {
        "ad": Noul(
            instructions=(
                "Is `title` plus `snippet` a pure advertisement, advertorial, "
                "sponsored post, or affiliate pitch rather than journalism?"
            ),
            criteria={
                "true": "The piece exists to sell a product, course, or brand. No independent news.",
                "false": "It is reporting, analysis, or opinion journalism, even if a company is mentioned.",
            },
        ),
        "clickbait": Noul(
            instructions=(
                "Does `title` oversell or withhold what `snippet` actually delivers?"
            ),
            criteria={
                "true": "Clickbait, curiosity-gap, or a headline that does not match the facts.",
                "false": "The title fairly describes the story.",
            },
        ),
        "press_release": Noul(
            instructions=(
                "Is `snippet` mostly a company or government press release, lightly rewritten?"
            ),
            criteria={
                "true": "PR copy, product launch fluff, or an official statement with no reporting.",
                "false": "Independent reporting, even if it quotes officials.",
            },
        ),
        "paywall_teaser": Noul(
            instructions=(
                "Is this a paywall teaser, subscribe wall, or lede-only fragment? "
                "Use `snippet` and `body_chars`, not a full article."
            ),
            criteria={
                "true": "Too little body to read; subscribe/paywall language or a snippet echo.",
                "false": "There is enough article text to read on a Kindle.",
            },
        ),
        "tipo": Choice(
            instructions=(
                "Given `snippet` and `body_chars`, is this a short teaser (`resumo`) or enough text to read "
                "(`artigo-completo`)? Ignore feed folders."
            ),
            criteria={
                "resumo": "Paywall teaser, lede-only, or too short to read as an article.",
                "artigo-completo": "Enough body to read on a Kindle.",
            },
        ),
    }
    for qid, tema in tema_map.items():
        questions[qid] = Noul(
            instructions=(
                f"Should this story be tagged `{tema}` in Portuguese topic tags? "
                "Use `title` and `snippet`. Multiple tags may be true."
            ),
            criteria={
                "true": f"The story is substantially about {tema}.",
                "false": f"The story is not about {tema}.",
            },
        )
    assert set(TIPOS) == {"resumo", "artigo-completo"}
    return questions
