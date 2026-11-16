"""Check that a URL serves an RSS or Atom feed, with the pipeline's parser (feedparser).

Users type these URLs, so the server only fetches public http(s) addresses on the
standard ports: every host, including each redirect target, must resolve to
public IPs only (no loopback, private, link-local, reserved or multicast).
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import feedparser
import requests

TIMEOUT_SECONDS = 10
MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
ALLOWED_SCHEMES = {"http": 80, "https": 443}
ALLOWED_PORTS = {80, 443}
USER_AGENT = "BiteSIze feed check (+https://github.com/victor-salles/bitesize)"


class FeedError(Exception):
    """The URL could not be fetched or is not a feed. The message is shown to the user."""


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop an IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved)


def check_public_url(url: str) -> None:
    """Raise FeedError unless `url` is http(s) on port 80/443 and its host resolves to public IPs only."""
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES or not parts.hostname:
        raise FeedError("A feed address must start with http:// or https://.")
    try:
        port = parts.port
    except ValueError:
        port = -1
    if port is not None and port not in ALLOWED_PORTS:
        raise FeedError("A feed must use the standard web ports (80 or 443).")
    try:
        infos = socket.getaddrinfo(parts.hostname, port or ALLOWED_SCHEMES[parts.scheme], type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise FeedError("Could not find that address.") from exc
    if not infos or not all(_is_public(info[4][0]) for info in infos):
        raise FeedError("That address points to a private network, which a feed cannot use.")


def _download(url: str) -> bytes:
    for _hop in range(MAX_REDIRECTS + 1):
        check_public_url(url)
        response = _get(url)
        if not response.is_redirect:
            return _read_body(response)
        response.close()
        url = urljoin(url, response.headers["Location"])
    raise FeedError("That address redirected too many times.")


def _get(url: str) -> requests.Response:
    # Redirects are followed by _download so every hop is checked; the residual
    # risk is DNS changing between the check and requests' own lookup.
    try:
        return requests.get(
            url,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
            stream=True,
        )
    except requests.Timeout as exc:
        raise FeedError(f"The site did not answer within {TIMEOUT_SECONDS} seconds.") from exc
    except requests.RequestException as exc:
        raise FeedError("Could not reach that address.") from exc


def _read_body(response: requests.Response) -> bytes:
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
