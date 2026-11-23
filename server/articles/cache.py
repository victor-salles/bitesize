"""The article cache: AI output per article URL and language, shared by every user.

Implements `pipeline.ArticleCache` on top of `core.Article`.
"""

import hashlib
from typing import Optional

from core.models import Article
from gemini import OPTIONAL_AI_FIELDS


def _text(art: dict) -> str:
    # The AI reads the body, or the title when no body was fetched.
    return art.get("content") or art.get("title") or ""


def text_hash(art: dict) -> str:
    return hashlib.sha256(_text(art).encode("utf-8")).hexdigest()


class DatabaseArticleCache:
    def get(self, art: dict, language: str) -> Optional[dict]:
        row = Article.objects.filter(url=art["url"], language=language).first()
        if row is None or row.text_hash != text_hash(art):
            return None
        if row.skipped:
            return {"skip": True}
        if row.score is None:
            return None
        return {
            "skip": False,
            "summary": row.summary,
            "relevance": int(row.score),
            "tipo": row.tags.get("tipo"),
            "temas": list(row.tags.get("temas", [])),
            # Rows are shared across users and outlive prompt changes: a missing field stays missing.
            **{key: row.tags[key] for key in OPTIONAL_AI_FIELDS if row.tags.get(key)},
        }

    def put(self, art: dict, language: str, result: dict) -> None:
        skipped = bool(result.get("skip"))
        Article.objects.update_or_create(
            url=art["url"],
            language=language,
            defaults={
                "title": (art.get("title") or "")[:500],
                "source": (art.get("source") or "")[:120],
                "text_length": len(_text(art)),
                "text_hash": text_hash(art),
                "skipped": skipped,
                "summary": "" if skipped else result.get("summary", ""),
                "score": None if skipped else result.get("relevance"),
                "tags": {} if skipped else {
                    "tipo": result.get("tipo"),
                    "temas": list(result.get("temas", [])),
                    **{key: result[key] for key in OPTIONAL_AI_FIELDS if result.get(key)},
                },
            },
        )
