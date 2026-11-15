"""Check that a URL serves an RSS or Atom feed, with the pipeline's parser (feedparser)."""

import feedparser
import requests

TIMEOUT_SECONDS = 10
MAX_BYTES = 5 * 1024 * 1024
USER_AGENT = "BiteSIze feed check (+https://github.com/victor-salles/bitesize)"


class FeedError(Exception):
    """The URL could not be fetched or is not a feed. The message is shown to the user."""


def _download(url: str) -> bytes:
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            stream=True,
        )
    except requests.Timeout as exc:
        raise FeedError(f"The site did not answer within {TIMEOUT_SECONDS} seconds.") from exc
    except requests.RequestException as exc:
        raise FeedError("Could not reach that address.") from exc
    try:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise FeedError(f"The site answered with an error ({response.status_code}).") from exc
        body = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise FeedError("That address returned a response too large to be a feed.")
        except requests.RequestException as exc:
            raise FeedError("The download was interrupted.") from exc
        return bytes(body)
    finally:
        response.close()


def validate_feed(url: str) -> str:
    """Fetch `url` and return the feed's title (may be empty). Raise FeedError if it is not RSS/Atom."""
    parsed = feedparser.parse(_download(url))
    if not parsed.version:
        raise FeedError("That address is not an RSS or Atom feed.")
    return (parsed.feed.get("title") or "").strip()
