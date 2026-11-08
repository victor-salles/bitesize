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
