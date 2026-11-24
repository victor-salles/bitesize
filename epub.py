from datetime import datetime
from pathlib import Path

from ebooklib import epub

from ai_locale import ai_language_code, epub_label, format_digest_date
from cover_art import render_cover
from cover_data import build_cover_data
from edition_data import EditionMeta, StoryNumbers
from article_page import ARTICLE_CSS, article_body
from epub_images import book_images
from epub_pages import CONTENTS_FILE, PAGES_CSS, BookLayout, contents_body, section_body, section_file
from topics_page import TOPICS_CHART_FILE, TOPICS_CSS, TOPICS_FILE, topics_body, topics_chart_png, topics_data
from magazine_layers import find_hero_article
from xhtml import safe_href, slugify, xhtml_page  # noqa: F401 (safe_href: tests import it from here)

_CSS = """
/* Kindle-friendly typography — all sizes in em so the device font slider works */
html {
  font-size: 100%;
  -webkit-text-size-adjust: 100%;
}

@page {
  margin: 3%;
}

body {
  font-family: "Bookerly", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
  font-size: 1em;
  line-height: 1.65;
  color: #1a1a1a;
  margin: 0;
  padding: 0 2%;
  text-align: left;
  -webkit-hyphens: auto;
  hyphens: auto;
}

h1, h2, h3, h4 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.25;
  font-weight: bold;
  hyphens: none;
  -webkit-hyphens: none;
}

h1 {
  font-size: 1.55em;
  border-bottom: 0.12em solid #333;
  padding-bottom: 0.3em;
  margin: 0 0 0.9em 0;
}

h2 { font-size: 1.3em; margin: 0.4em 0 0.5em 0; }
h3 { font-size: 1.12em; margin: 0 0 0.25em 0; }
h4 { font-size: 1em; margin: 0 0 0.2em 0; }

p { margin: 0 0 0.75em 0; text-align: justify; }

a { color: #111111; text-decoration: none; }

/* ── Article body: the reader's font, size and spacing (HANDOFF rule 2) ─── */
.article-body { margin-top: 1em; }
.article-body p { margin: 0 0 0.75em 0; }
"""


def generate_epub(
    sections: dict[str, list[dict]],
    section_covers: dict[str, dict],
    global_cover: dict,
    output_path: Path,
    meta: EditionMeta | None = None,
) -> None:
    meta = meta or EditionMeta(now=datetime.now())
    book = epub.EpubBook()
    now  = meta.now

    lang = ai_language_code()
    digest = epub_label("digest_title")
    contents = epub_label("contents")

    book.set_identifier(f"bitesize-{now.strftime('%Y%m%d%H%M%S')}")
    book.set_title(f"{digest} – {format_digest_date(now)} {now.strftime('%H:%M')}")
    book.set_language(lang)
    book.add_author("BiteSIze")

    hero, hero_category = find_hero_article(sections, global_cover)
    cover_headline = (global_cover or {}).get("headline") or ""
    if not cover_headline and hero:
        cover_headline = hero.get("title", digest)
    if not cover_headline:
        cover_headline = digest
    numbers = StoryNumbers(sections)
    cover_jpeg = render_cover(
        build_cover_data(sections, cover_headline, hero, hero_category, numbers, meta),
        meta.cover_style,
    )
    # Metadata-only cover image for Kindle library shelf (create_page=False).
    book.set_cover("cover.jpg", cover_jpeg, create_page=False)

    css_item = epub.EpubItem(
        uid="style", file_name="style.css",
        media_type="text/css", content=_CSS + PAGES_CSS + TOPICS_CSS + ARTICLE_CSS,
    )
    book.add_item(css_item)

    for name, data in book_images().items():
        book.add_item(epub.EpubItem(uid=slugify(name), file_name=name, media_type="image/png", content=data))

    layout = BookLayout(sections)
    cover_ch = epub.EpubHtml(title=contents, file_name=CONTENTS_FILE, lang=lang)
    cover_ch.content = xhtml_page(contents, contents_body(layout, hero, hero_category, meta))
    cover_ch.add_item(css_item)
    book.add_item(cover_ch)

    # Cover first: if `nav` is linear, Kindle opens the NCX link tree (unreadable).
    # Keep the nav document for the TOC button, but mark it non-linear in the spine.
    spine: list = [cover_ch, ("nav", "no")]
    toc: list = [epub.Link(CONTENTS_FILE, contents, "contents")]

    topics = topics_data(layout, meta.previous_topic_counts)
    if topics.rows:
        book.add_item(epub.EpubItem(uid="topics_chart", file_name=TOPICS_CHART_FILE, media_type="image/png",
                                    content=topics_chart_png(topics)))
        topics_title = epub_label("edition_topics")
        topics_ch = epub.EpubHtml(title=topics_title, file_name=TOPICS_FILE, lang=lang)
        topics_ch.content = xhtml_page(topics_title, topics_body(topics, layout, meta))
        topics_ch.add_item(css_item)
        book.add_item(topics_ch)
        spine.append(topics_ch)
        toc.append(epub.Link(TOPICS_FILE, topics_title, "topics"))

    for category, articles in sections.items():
        if not articles:
            continue

        slug = slugify(category)
        section_ch = epub.EpubHtml(title=category, file_name=section_file(category), lang=lang)
        section_ch.content = xhtml_page(category, section_body(category, layout))
        section_ch.add_item(css_item)
        book.add_item(section_ch)
        spine.append(section_ch)
        section_links: list = [epub.Link(section_file(category), category, f"section_{slug}")]

        for i, art in enumerate(articles, start=1):
            art_slug = f"{slug}_{i:02d}"
            art_ch = epub.EpubHtml(
                title=art["title"],
                file_name=f"article_{art_slug}.xhtml",
                lang=lang,
            )
            art_ch.content = xhtml_page(art["title"], article_body(art, layout))
            art_ch.add_item(css_item)
            book.add_item(art_ch)
            spine.append(art_ch)
            section_links.append(
                epub.Link(f"article_{art_slug}.xhtml", art["title"], f"art_{art_slug}")
            )

        toc.append((epub.Section(category), tuple(section_links)))

    book.toc   = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book)
