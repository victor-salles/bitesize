# Jev + dashboard handoff

For an agent building an **email client** that classifies with Jev and reviews results in a local dashboard like BiteSize. This repo is the working example, not a template to copy wholesale. Digest EPUB, Kindle, and RSS stay here.

**Done when** the new app: (1) calls Jev as a scorer on a tiny payload, (2) applies skip/keep in code after scores, (3) writes every run to JSON, (4) shows those runs in a local table with meters, pills, filters, sort, and collapsible groups.

## Jev is a scorer, not a writer

Jev (TypeSafe System One) returns independent judgments in one call: Noul (0–1), Score (ordered levels), Choice (one of a fixed set). It does not write summaries, HTML, or mail bodies. A writing model, if any, stays a separate step.

Need `TYPESAFE_API_KEY` in the environment. SDK: `typesafe_sdk` (`TypeSafeClient().system_one(state=…, questions=…)`).

**State (what the model reads)** — only what the questions need. BiteSize sends `title`, `source`, a ~480-character `snippet`, and `body_chars`. No full body, URL, or feed folder. Email should send the same *kind* of thing: subject, from, a snippet of the body, maybe thread size — not the whole MIME message.

**Questions** — all independent questions in one System One call. BiteSize: ads, keep, clickbait, press release, paywall, relevance, tipo, one Noul per tema. Email will need a **new question set** (spam, newsletter, needs-reply, urgency, folder, …). Copy the *shape*, not the news prompts.

**Policy after answers** — thresholds live in code, not in the prompt. Map scores to skip/archive/keep, tags, and a 0–100 rank. Tune numbers without another Jev call.

**Persist every run** as JSON (BiteSize: `output/jev/<id>.json`). The dashboard only reads those files. Include per-item answers, usage tokens, skip reason, and the original snippet you sent.

Read in this repo: `jev_questions.py`, `jev_policy.py`, `jev_triage.py`, `jev_log.py`. Tests: `tests/test_jev_triage.py`.

## Dashboard pattern

Local Flask, bind `127.0.0.1`. GET APIs for listing/loading runs; Bearer token only for writes. Secrets stay off git.

**Look:** Tailwind CDN with `preflight: false` so existing CSS still works. Cards, slate borders, small type. Table + sticky run sidebar (counts, kept bar, token totals, selected-row JSON).

**Numbers as meters, not raw floats.** Relevance = horizontal bar. Keep/ad = small ring + percent. High ad uses a red ring.

**Tags as pills.** Same rounded chip as tipo (`completo` / `resumo`). Color by vocabulary, not a comma list.

**Review tools on the table, not a second page:** search; dropdowns for source/tipo/tema/skip; sliders for min/max relevance, min keep, max ad; group by source (or equivalent); click a column header to sort (click again to reverse); click a group name to collapse (taller group row, chevron + count). Client-side over the loaded JSON.

Read: `dashboard_static/app.js` (`article_state` is Python; UI lives in `paintJevRows`, `jevFilter`, `jevSort`, `jevCollapsed`), `dashboard_static/index.html`, `dashboard.py` Jev routes.

## Email client — reuse vs invent

Reuse: scorer vs writer, tiny state, one System One call, policy in code, JSON run log, local table with meters/pills/filter/sort/collapse.

Invent: IMAP/Gmail fetch, thread vs message as the row, email-specific questions, what “skip” means (archive, mute, spam), whether the operator can override a judgment and write that back.

Single-user local tool. Do not expose the dashboard. Do not put API keys in the JSON you show in the UI.
