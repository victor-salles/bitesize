"""What an edition build needs from this app: the server's AI client and the article cache."""

from .cache import DatabaseArticleCache
from .gemini import GeminiClient


def get_server_ai_client() -> GeminiClient:
    """`EditionConfig.ai`: Gemini with the server key and daily cap from settings."""
    return GeminiClient.from_settings()


def get_article_cache() -> DatabaseArticleCache:
    """`EditionConfig.article_cache`: AI output shared by every user, per URL and language."""
    return DatabaseArticleCache()
