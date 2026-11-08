# Documentation screenshots

Retakes every picture in `docs/screenshots/`. The dashboard shots come from a clean database, and the book shots come from a demo EPUB with made-up stories. Neither needs your settings, your feeds or an AI backend.

Run from a fresh worktree, so `data/` and `.env` are empty:

```bash
git worktree add ../bitesize-shots origin/main && cd ../bitesize-shots
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. Demo book
.venv/bin/python scripts/doc-screenshots/demo_digest.py /tmp/shots/demo.epub
unzip -o /tmp/shots/demo.epub -d /tmp/shots/book

# 2. Dashboard on the clean database
DASHBOARD_TOKEN=demo .venv/bin/python dashboard.py &

# 3. Capture (uses the installed Google Chrome)
npm i --no-save playwright-core
node scripts/doc-screenshots/capture.js /tmp/shots/book
```

The PNGs land in `docs/screenshots/`. Check them before committing, then stop the dashboard.

- **Change what gets shot:** edit `screens.js`.
- **Change the demo stories:** edit `demo_digest.py`.
- **Sizes:** the dashboard is shot at 1440×900, and book pages at Kindle Paperwhite proportions (618×824 CSS px). All shots are at 2× scale.
