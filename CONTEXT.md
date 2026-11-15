# BiteSize

A single-user local news digest: feeds become a magazine EPUB, then optional Kindle and Books delivery.

## Language

**Digest**:
The Python pipeline from RSS (and optional Gmail or Calendar) to a magazine EPUB.
_Avoid_: App (when you mean this pipeline), product, service

**Dashboard**:
The local Flask UI for settings, sources, and Preview. Binds to the machine it runs on.
_Avoid_: Web app, admin, settings site

**Preview**:
The dashboard tab that lists live headlines from configured sources.
_Avoid_: Digest preview (that is a later, unbuilt idea)

**Phase**:
An optional capability that works when its settings are present and is skipped when they are not: Dashboard, local EPUB, Kindle send, Books copy, Gmail, Calendar.
_Avoid_: Feature flag, integration (when you mean a phase), required step

**Operator**:
A person running the Digest on their own machine — the author or someone they shared the private repo with.
_Avoid_: User (when you mean the person who runs it), customer, contributor

**Hiring reader**:
A person reviewing the private repo as a portfolio piece.
_Avoid_: Open-source user, community, contributor

**Ready**:
The private repo meets the share bar: coverage above 95% on the Digest, the dashboard server, and the dashboard browser code; documentation with a how-it-works page; README screenshots of the real interface; only app code in the tree.
_Avoid_: Open-source ready, public, launched

**Seed**:
The first-run values in `.env` and `sources.json`. After the first migrate, the local database is the source of truth.
_Avoid_: Config (when you mean the live database settings)

**Server**:
The multi-user Django app in `server/` that runs the Digest once per user. See `docs/adr/0001-django-server.md`.
_Avoid_: Dashboard (that is the local Flask UI), backend

**Source**:
One RSS feed a user follows, filed under a category. A user's active sources become `EditionConfig.sources`.
_Avoid_: Feed (when you mean the user's saved entry), subscription

**Edition**:
One user's Digest for one date: its place in the queue, the EPUB it built, and whether it reached the Kindle. One per user per date.
_Avoid_: Run, job, issue (of a magazine)

**Article cache**:
AI output (summary, score) stored per article URL and language, shared by every user whose Edition includes that article.
_Avoid_: Article (when you mean a user's copy), summary store
