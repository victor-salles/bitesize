"""XHTML helpers shared by the EPUB page builders."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from ai_locale import ai_language_code


def escape(s: str) -> str:
    return html.escape(s or "")


_ALLOWED_SCHEMES = {"http", "https"}


def safe_href(url: str) -> str:
    """Return HTML-escaped http(s) URL, or empty string if unsafe."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return ""
    return escape(url)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def xhtml_page(title: str, body: str) -> bytes:
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{ai_language_code()}">'
        "<head>"
        f"  <title>{escape(title)}</title>"
        '  <meta charset="utf-8"/>'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
        '  <link href="style.css" rel="stylesheet" type="text/css"/>'
        "</head>"
        f"<body>{body}</body>"
        "</html>"
    ).encode("utf-8")
