"""Check that a URL serves an RSS or Atom feed, with the pipeline's parser (feedparser).

Users type these URLs, so the fetch goes through `safe_fetch`: public http(s)
addresses on the standard ports only, checked again on every redirect.
"""

import feedparser

import safe_fetch
from safe_fetch import FetchError, Reason

TIMEOUT_SECONDS = 10
MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = "BiteSIze feed check (+https://github.com/victor-salles/bitesize)"

MESSAGES = {
    Reason.SCHEME: "A feed address must start with http:// or https://.",
    Reason.PORT: "A feed must use the standard web ports (80 or 443).",
    Reason.UNRESOLVED: "Could not find that address.",
    Reason.PRIVATE: "That address points to a private network, which a feed cannot use.",
    Reason.TOO_MANY_REDIRECTS: "That address redirected too many times.",
    Reason.TIMEOUT: f"The site did not answer within {TIMEOUT_SECONDS} seconds.",
    Reason.UNREACHABLE: "Could not reach that address.",
    Reason.TOO_LARGE: "That address returned a response too large to be a feed.",
    Reason.INTERRUPTED: "The download was interrupted.",
}


class FeedError(Exception):
    """The URL could not be fetched or is not a feed. The message is shown to the user."""


def _message(error: FetchError) -> str:
    if error.reason is Reason.HTTP_ERROR:
        return f"The site answered with an error ({error.status_code})."
    return MESSAGES[error.reason]


def _download(url: str) -> bytes:
    try:
        return safe_fetch.fetch(
            url,
            timeout=TIMEOUT_SECONDS,
            user_agent=USER_AGENT,
            max_bytes=MAX_BYTES,
            max_redirects=MAX_REDIRECTS,
        )
    except FetchError as exc:
        raise FeedError(_message(exc)) from exc


def validate_feed(url: str) -> str:
    """Fetch `url` and return the feed's title (may be empty). Raise FeedError if it is not RSS/Atom."""
    parsed = feedparser.parse(_download(url))
    if not parsed.version:
        raise FeedError("That address is not an RSS or Atom feed.")
    return (parsed.feed.get("title") or "").strip()
