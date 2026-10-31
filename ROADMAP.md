# Roadmap

What the digest does today, and what is worth building next. Bugs and flakes live in [ISSUES.md](ISSUES.md).

## Shipped

The morning pipeline is in daily use: RSS → full text → AI filter/summarize/score → magazine EPUB → Kindle email and iCloud Books.

- **Settings live in SQLite** (`data/bitesize.db`), edited from the local dashboard. `.env` / `sources.json` only seed an empty database.
- **Three AI backends:** Antigravity (`agy`, default), Gemini CLI, Ollama. If none answer, the EPUB still writes with length-based scores and no summaries.
- **Optional Jev triage:** TypeSafe scores ads, compiled relevance (0–100 from ranked theme matches), `resumo` vs `artigo-completo`, and pt-BR temas. Reader topic order in the dashboard sets rank (1 = strongest). Each call sends title, source, a ~480-character snippet, and `body_chars` — not the full article. Off until `jev_triage_enabled` is on and a TypeSafe or Vercel AI Gateway key is in `.env`. Gateway `vck_…` keys go to `ai-gateway.vercel.sh`. The gateway free tier no longer serves Jev; use a TypeSafe console key (see ISSUES.md). The writing model still writes summaries and covers.
- **pt-BR labels and prompts** (`ai_locale.py`). Language is a setting, not a rewrite of the pipeline.
- **Paywall mirrors** when the direct fetch is thin or fails.
- **Gmail and Calendar sections** are wired in `main.py` and off by default. Enable them in the dashboard; the daily `--all` run will pick them up.
- **macOS LaunchAgent** at 06:50 (`scripts/install-daily-launchd.sh`).
- **pt-BR tags** on each story: `resumo` vs `artigo-completo`, plus temas from a fixed list. Heuristics run when the AI is down.
- **Scoring:** fallback stays below 70; cover and section leads prefer AI scores over length stand-ins; clustered AI batches get one listwise re-rank.
- **Open-source hygiene:** MIT license, `SECURITY.md`, pytest + coverage + pip-audit + gitleaks CI, Dependabot, GitHub issue templates.

The dashboard **Preview** tab now loads live headlines per source. The header **Run digest** button starts the same `--all` job as the morning run and lists each pipeline step with a live log. **Jev** tab lists each classify run and the JSON file under `output/jev/`. English chrome by default (`ui_language` / localStorage); Rel, Ad, and per-theme scores use percent + bar (no Keep column or rel/keep/ad filter sliders). You can correct Ad, Rel, Tipo, Temas, and the extra scores per story; **Export labels** writes a gold file for later question/threshold work. Still missing: last-digest preview, AI summary preview, magazine cover preview, Jev field picker.

## Next

1. **A smaller morning book.** Daily runs land 120–140 articles. Relevance sorting exists; Jev `jev_min_keep` is a minimum compiled relevance (0–100) — `40` is a reasonable cutoff on the ranked-theme scale. A dedicated “top stories only” EPUB is still optional.

2. **Safari Reader on a rendered page.** A static Readability pass on the same GET bytes did **not** beat trafilatura (DROP — [experiment note](docs/research/2026-08-30-reader-extract-experiment.md)). The remaining bet is headless render, then extract. Background: [Safari Reader note](docs/research/2026-08-30-safari-reader-paywall.md).

3. **Dashboard previews (still open).** Last digest, a sample AI summary, and the cover JPEG before send. Headline-per-source preview is already in the Preview tab.

4. **Hourly pool, two builds a day.** Fetch through the day; assemble a short morning book and a short evening book. Mentioned as the next plan, not written yet.

5. **Gmail and Calendar on the daily run.** Code is ready; flags are still off. Needs Google OAuth files on the machine (`credentials.json` / `token.json`).

6. **Stock-Kindle navigation, not scripts.** Internal links, a better opening page, maybe clippings later. JavaScript, forms, and quizzes will not run on an unmodified Kindle — see `docs/research/2026-08-14-kindle-interactive-epub.md`. Type and magazine hierarchy on that page: [VIC-14](https://linear.app/victor-salles/issue/VIC-14/opening-page-should-feel-like-a-magazine-cover).

7. **Kindle library cleanup is manual.** Amazon has no auto-delete for Send-to-Kindle personal documents. See [docs/research/2026-08-30-kindle-auto-delete.md](docs/research/2026-08-30-kindle-auto-delete.md).

## Later

- Fail-closed dashboard reads on a shared Mac (writes already need a token).
- Wordflow as its own product, or dropped. It is not part of the digest.

## Won't

- Interactive EPUB quizzes or in-book JavaScript on stock Kindle.
- Treating RSS URLs as untrusted-by-default (this is a personal digest; you pick the feeds).
