"""Template context shared by every page."""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class Tab:
    label: str
    url: str
    current: bool


# (label, URL name, the URL names or namespaces that belong to the tab), in display order.
TABS = (
    ("Sources", "sources:list", {"sources"}),
    ("Delivery", "delivery", {"delivery"}),
    ("Editions", "editions:status", {"editions"}),
    ("Account", "account", {"account", "invites"}),
)


def _section(request) -> str | None:
    match = getattr(request, "resolver_match", None)
    if match is None:
        return None
    return match.namespace or match.url_name


def tabs(request) -> dict[str, list[Tab]]:
    """The tab navigation for logged-in readers, with the current page's tab marked."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"tabs": []}
    section = _section(request)
    return {"tabs": [Tab(label, reverse(name), section in members) for label, name, members in TABS]}
