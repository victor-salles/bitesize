"""Build one edition from explicit inputs.

build_edition() runs RSS -> full text -> AI -> covers -> EPUB and returns the
EPUB path. It never reads `.env` or `data/bitesize.db`: everything comes from
EditionConfig. Delivery (Kindle, Books) and fetching Gmail/Calendar stay with
the caller.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Protocol

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ai import AIClient, use_ai_client
from ai_locale import epub_label, format_digest_timestamp
from config import console, get_settings, submit_in_context, use_settings
from edition_data import EditionMeta, topic_mention_counts
from epub import generate_epub
from feed import fetch_article_content, fetch_feed, filter_headline_only
from safe_fetch import FetchError
from gemini import generate_global_cover, generate_section_cover, process_articles, spread_tied_scores
from magazine_layers import article_rank_sort_key
from paywall import log_summary, reset_stats
from settings_store import Settings
from tags import normalize_tags


@dataclass
class ExtraSection:
    """A prebuilt section (Inbox, Calendar) with its own cover builder."""

    name: str
    articles: list[dict]
    make_cover: Callable[[list[dict]], dict]


class ArticleCache(Protocol):
    """Per-article AI output (summary, score, tags) kept across editions.

    A result is {"skip": True} for an ad the AI dropped, otherwise
    {"summary", "relevance", "tipo", "temas"}. get() returns None on a miss
    or when the cached copy is stale.
    """

    def get(self, art: dict, language: str) -> Optional[dict]: ...

    def put(self, art: dict, language: str, result: dict) -> None: ...


@dataclass
class EditionConfig:
    # {category: {source name: feed URL}}
    sources: dict[str, dict[str, str]]
    output_dir: Path
    settings: Settings = field(default_factory=Settings)
    # Overrides for the matching Settings fields when set.
    language: Optional[str] = None
    max_articles_per_feed: Optional[int] = None
    # None routes AI calls by settings.ai_backend.
    ai: Optional[AIClient] = None
    # None runs AI on every article; the server shares one cache across users.
    article_cache: Optional[ArticleCache] = None
    extra_sections: list[ExtraSection] = field(default_factory=list)
    now: Optional[datetime] = None
    # The reader's Nth edition, shown as "Edição N"; None hides it.
    edition_number: Optional[int] = None
    # Topic mention counts of the reader's previous edition, for the "vs. ontem"
    # trend on the topics page; None hides the trend.
    previous_topic_counts: Optional[dict[str, int]] = None

    def effective_settings(self) -> Settings:
        overrides = {}
        if self.language is not None:
            overrides["ai_language"] = self.language
        if self.max_articles_per_feed is not None:
            overrides["max_articles_per_feed"] = self.max_articles_per_feed
        return dataclasses.replace(self.settings, **overrides)


@dataclass
class EditionResult:
    # None when nothing readable was left and no EPUB was written.
    epub_path: Optional[Path]
    raw_count: int = 0
    full_text_count: int = 0
    kept_count: int = 0
    filtered_count: int = 0
    article_count: int = 0
    section_counts: dict[str, int] = field(default_factory=dict)
    # {tema: mentions}: an article with two temas counts in both.
    topic_counts: dict[str, int] = field(default_factory=dict)


def _log_blocked(blocked: list[dict]) -> None:
    console.print(
        f"  [yellow]✗  skipped {len(blocked)} article(s) on a private or "
        f"non-web address:[/yellow]"
    )
    for art in blocked:
        console.print(f"    [dim]· {art['source']}: {art['url']}[/dim]")


def _log_headline_drops(dropped: list[dict]) -> None:
    if not dropped:
        return
    by_source = Counter(art["source"] for art in dropped)
    console.print(
        f"  [dim]✗  dropped {len(dropped)} headline-only "
        f"(no body text or summary):[/dim]"
    )
    for source, count in by_source.most_common():
        console.print(f"  [dim]   · {source}: {count}[/dim]")


def _process_articles(articles: list[dict], cache: Optional[ArticleCache]) -> list[dict]:
    """process_articles(), sending only articles missing from *cache* to the AI."""
    if cache is None:
        return process_articles(articles)

    language = get_settings().ai_language
    hits: list[dict] = []
    misses: list[dict] = []
    for art in articles:
        cached = cache.get(art, language) if art.get("url") else None
        if cached is None:
            misses.append(art)
        elif not cached.get("skip"):
            hit = {**art, "summary": cached.get("summary", ""), "relevance": cached["relevance"],
                   "relevance_source": "ai"}
            hits.append(normalize_tags(hit, cached))

    processed = process_articles(misses) if misses else []

    by_url = {art["url"]: art for art in processed if art.get("url")}
    for art in misses:
        if not art.get("url"):
            continue
        out = by_url.get(art["url"])
        if out is None:  # the AI dropped it as an ad
            cache.put(art, language, {"skip": True})
        elif out.get("relevance_source") == "ai":  # never cache fallback scores
            cache.put(art, language, {
                "summary": out.get("summary", ""),
                "relevance": out["relevance"],
                "tipo": out.get("tipo"),
                "temas": out.get("temas", []),
            })

    if hits:
        console.print(f"  [dim]♻  {len(hits)} article(s) from the article cache[/dim]")
    return spread_tied_scores(hits + processed)


def build_edition(config: EditionConfig) -> EditionResult:
    """Build one EPUB from *config*. Reads no global config."""
    with use_settings(config.effective_settings()), use_ai_client(config.ai):
        return _build(config)


def _build(config: EditionConfig) -> EditionResult:
    selected = config.sources
    extras = [x for x in config.extra_sections if x.articles]
    total_feeds = sum(len(v) for v in selected.values())

    # ── 1. Fetch feeds in parallel ────────────────────────────────────────────
    raw_sections: dict[str, list] = {cat: [] for cat in selected}
    fetched = 0

    if selected:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as prog:
            task = prog.add_task(f"Fetching {total_feeds} feeds…", total=total_feeds)

            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {
                    submit_in_context(pool, fetch_feed, name, url): cat
                    for cat, srcs in selected.items()
                    for name, url in srcs.items()
                }
                for fut in as_completed(futures):
                    cat = futures[fut]
                    articles = fut.result()
                    for art in articles:
                        art["category"] = cat
                    raw_sections[cat].extend(articles)
                    prog.advance(task)

    total_raw = sum(len(v) for v in raw_sections.values())
    if selected:
        console.print(f"[green]✓[/green]  Fetched [bold]{total_raw}[/bold] raw articles")

    # ── 2. Fetch full article content in parallel ─────────────────────────────
    if selected:
        flat_for_content = [art for arts in raw_sections.values() for art in arts]
        reset_stats()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as prog:
            task = prog.add_task(
                f"Fetching full content for {total_raw} articles…", total=total_raw
            )
            with ThreadPoolExecutor(max_workers=10) as pool:
                future_to_art = {
                    submit_in_context(pool, fetch_article_content, art["url"]): art
                    for art in flat_for_content
                }
                fetched = 0
                blocked: list[dict] = []
                for fut in as_completed(future_to_art):
                    art = future_to_art[fut]
                    try:
                        content = fut.result()
                    except FetchError as exc:
                        if not exc.blocked:
                            raise
                        blocked.append(art)
                        prog.advance(task)
                        continue
                    if content:
                        if not art.get("rss_snippet"):
                            art["rss_snippet"] = art.get("content", "")
                        art["content"] = content
                        fetched += 1
                    prog.advance(task)

        if blocked:
            _log_blocked(blocked)
            blocked_ids = {id(art) for art in blocked}
            for cat in raw_sections:
                raw_sections[cat] = [art for art in raw_sections[cat] if id(art) not in blocked_ids]
            total_raw -= len(blocked)

        console.print(
            f"[green]✓[/green]  Full content retrieved for "
            f"[bold]{fetched}[/bold] / {total_raw} articles"
            + (f" [dim]({total_raw - fetched} unavailable/paywalled)[/dim]"
               if fetched < total_raw else "")
        )
        log_summary(console, log_dir=Path(config.output_dir) / "logs")

    # ── 3. AI processing ──────────────────────────────────────────────────────
    kept_flat: list[dict] = []
    processed_sections: dict[str, list] = {}

    if selected:
        console.print()
        console.print("[cyan]🤖  Running AI processing…[/cyan]")

        flat_articles = [art for arts in raw_sections.values() for art in arts]

        with console.status("  Filtering and summarising articles…"):
            processed_flat = _process_articles(flat_articles, config.article_cache)

        # ── 3.5 Drop headline-only articles (no readable body or summary) ─────
        kept_flat, dropped_flat = filter_headline_only(processed_flat)
        _log_headline_drops(dropped_flat)

        processed_sections = {cat: [] for cat in selected}
        for art in kept_flat:
            cat = art.get("category", "")
            if cat in processed_sections:
                processed_sections[cat].append(art)

        # Highest relevance first within each section (Kindle spine + indexes follow this order).
        for cat in processed_sections:
            processed_sections[cat].sort(key=article_rank_sort_key)

        total_filtered = total_raw - len(kept_flat)
        console.print(
            f"  [green]✓[/green]  [bold]{len(kept_flat)}[/bold] articles kept"
            + (f", [dim]{total_filtered} filtered[/dim]" if total_filtered else "")
        )

    for extra in extras:
        processed_sections[extra.name] = extra.articles

    result = EditionResult(
        epub_path=None,
        raw_count=total_raw,
        full_text_count=fetched,
        kept_count=len(kept_flat),
        filtered_count=total_raw - len(kept_flat),
    )

    if not kept_flat and not extras:
        console.print("[yellow]No readable articles left — exiting.[/yellow]")
        return result

    # ── 4. Generate section covers ────────────────────────────────────────────
    console.print()
    console.print("[cyan]📰  Generating section covers…[/cyan]")

    extra_names = {x.name for x in extras}
    section_covers: dict[str, dict] = {}
    for cat, articles in processed_sections.items():
        if cat in extra_names or not articles:
            continue
        with console.status(f"  {cat}…"):
            section_covers[cat] = generate_section_cover(cat, articles)
        status = "✓" if section_covers[cat] else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  {cat}")

    for extra in extras:
        with console.status(f"  {extra.name}…"):
            section_covers[extra.name] = extra.make_cover(extra.articles)
        status = "✓" if section_covers.get(extra.name) else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  {extra.name}")

    # ── 5. Generate global cover ──────────────────────────────────────────────
    with console.status("  Global cover…"):
        global_cover = generate_global_cover(section_covers)
    console.print(
        f"  [green]{'✓' if global_cover else '⚠ fallback'}[/green]  Global cover"
    )

    # ── 6. Generate EPUB ──────────────────────────────────────────────────────
    console.print()
    now      = config.now or datetime.now()
    filename = f"{epub_label('digest_title')} - {format_digest_timestamp(now)}.epub"
    out_path = Path(config.output_dir) / filename

    with console.status("[cyan]Generating EPUB…[/cyan]"):
        generate_epub(
            processed_sections, section_covers, global_cover, out_path,
            meta=EditionMeta(
                now=now,
                edition_number=config.edition_number,
                previous_topic_counts=config.previous_topic_counts,
            ),
        )

    total_final = sum(len(v) for v in processed_sections.values())
    console.print(f"\n[bold green]✅  Done![/bold green]  {total_final} articles saved.")
    console.print(f"   [dim]{out_path}[/dim]\n")

    result.epub_path = out_path
    result.article_count = total_final
    result.section_counts = {cat: len(arts) for cat, arts in processed_sections.items()}
    result.topic_counts = topic_mention_counts(processed_sections)
    return result
