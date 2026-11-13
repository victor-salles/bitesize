#!/usr/bin/env python3
"""
BiteSIze — AI-powered personal news digest for Kindle.

Usage:
    python3 main.py

Interactively select categories and sources, then fetches RSS feeds,
filters ads and generates AI summaries via Gemini CLI, and produces
a Kindle-friendly EPUB in the ./output/ folder.
"""

import argparse
import sys

from config import console, get_settings, load_env, OUTPUT_DIR
from pipeline import EditionConfig, ExtraSection, build_edition
from books import copy_to_icloud_books
from kindle import send_to_kindle
from gmail import get_gmail_threads
from gmail_processor import process_email_threads, generate_inbox_cover
from calendar_fetch import get_calendar_events
from calendar_processor import format_calendar_section, generate_calendar_cover
import settings_store
from sources_selection import build_selected_sources, sources_config_from_settings
from ui import select_integrations


def main() -> None:
    parser = argparse.ArgumentParser(description="BiteSIze news digest for Kindle")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all categories and sources without prompting",
    )
    parser.add_argument(
        "--no-kindle",
        action="store_true",
        help="Write EPUB only; skip SMTP delivery to Kindle",
    )
    parser.add_argument(
        "--no-books",
        action="store_true",
        help="Skip copying the EPUB to the iCloud Books library",
    )
    args = parser.parse_args()

    load_env()
    settings = get_settings()
    sources_tree = settings_store.load_sources_tree(enabled_only=True)
    full_config = sources_config_from_settings(settings, sources_tree or {})
    integrations = dict(full_config.get("integrations", {}))
    if not (args.all or settings.cli_select_all_sources):
        integrations = select_integrations(full_config)

    if not sources_tree and not any(integrations.values()):
        console.print(
            "[red]Error:[/red] No RSS sources configured. "
            "Run [bold]python dashboard.py[/bold] to add feeds."
        )
        sys.exit(1)

    selected = build_selected_sources(settings, args, sources_tree or {})

    if not selected and not any(integrations.values()):
        console.print("[yellow]No sources selected — exiting.[/yellow]")
        return

    inbox_articles: list[dict] = []
    if integrations.get("gmail"):
        console.print("[cyan]Fetching Gmail…[/cyan]")
        with console.status("  Fetching threads…"):
            threads = get_gmail_threads(
                settings.gmail_max_threads,
                settings.gmail_lookback_hours,
            )
        if threads:
            console.print(f"  [green]✓[/green]  {len(threads)} threads fetched")
            with console.status("  Triaging inbox…"):
                inbox_articles = process_email_threads(threads)
            if inbox_articles:
                console.print(
                    f"  [green]✓[/green]  {len(inbox_articles)} threads kept"
                )
        else:
            console.print(
                "  [yellow]⚠  No Gmail threads — skipping Inbox section[/yellow]"
            )

    calendar_articles: list[dict] = []
    if integrations.get("google_calendar"):
        console.print("[cyan]Fetching Google Calendar…[/cyan]")
        with console.status("  Fetching events…"):
            events = get_calendar_events(
                settings.calendar_lookahead_days,
                settings.calendar_lookback_days,
            )
        total_events = len(events.get("today", [])) + len(events.get("upcoming", []))
        if total_events:
            console.print(f"  [green]✓[/green]  {total_events} events fetched")
            with console.status("  Formatting calendar…"):
                calendar_articles = format_calendar_section(events)
        else:
            console.print(
                "  [yellow]⚠  No calendar events — skipping Calendar section[/yellow]"
            )

    extra_sections: list[ExtraSection] = []
    if inbox_articles:
        extra_sections.append(ExtraSection("Inbox", inbox_articles, generate_inbox_cover))
    if calendar_articles:
        extra_sections.append(
            ExtraSection("Calendar", calendar_articles, generate_calendar_cover)
        )

    result = build_edition(
        EditionConfig(
            sources=selected,
            output_dir=OUTPUT_DIR,
            settings=settings,
            extra_sections=extra_sections,
        )
    )
    out_path = result.epub_path
    if out_path is None:
        return

    # ── 7. Send to Kindle ─────────────────────────────────────────────────────
    if args.no_kindle or not settings.kindle_delivery_enabled:
        reason = "--no-kindle" if args.no_kindle else "kindle_delivery_enabled=false"
        console.print(f"[dim]  Skipped Kindle delivery ({reason}).[/dim]")
    else:
        console.print("[cyan]📬  Sending to Kindle…[/cyan]")
        send_to_kindle(out_path, settings)

    # ── 8. Copy to iCloud Books (syncs to iPhone via iCloud) ──────────────────
    if args.no_books or not settings.books_delivery_enabled:
        reason = "--no-books" if args.no_books else "books_delivery_enabled=false"
        console.print(f"[dim]  Skipped iCloud Books copy ({reason}).[/dim]")
    else:
        console.print("[cyan]📚  Copying to iCloud Books…[/cyan]")
        copy_to_icloud_books(out_path, settings)


if __name__ == "__main__":
    main()
