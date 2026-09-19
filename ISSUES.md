# Issues

Open problems seen in the running app. There is no GitHub issue tracker yet. Close an item here when it is no longer true.

## Antigravity flakes during the daily run

**Expected:** Filter, summaries, and covers come back from `agy`.  
**Actual (19 Sep 2026):** Every `agy` call exited 1 with `invalid model selection` for `gemini-3.5-flash-medium`. That id is gone from `agy models` (now 3.6–3.8 Flash). The digest still wrote, with no summaries and placeholder covers.

**Landed:** Retired 3.5 Flash ids map to the matching 3.8 Flash id at call time. Default setting is `gemini-3.8-flash-high`.

Older morning logs (29–30 August) still had mixed `exited 1` / `status 'ERROR'` on large batches; keep an eye on timeouts after the model id is valid.

## Preview showed “No headlines” for every source

**Expected:** Preview lists recent titles per feed.  
**Actual:** Every source said “No headlines returned.” The dashboard process had inherited an HTTP proxy (`127.0.0.1:61630`) that rejected RSS tunnels with 403. Failed downloads also returned an empty list, so the UI hid the error.

**Landed:** RSS fetch ignores env proxies; Preview treats a failed download as an error, not an empty feed.

## AP News feed returns 403

**Expected:** The World “AP News” source contributes headlines.  
**Actual:** Fetch logs `403 Forbidden` for `https://apnews.com/hub/apf-topnews?format=rss`. The other World feeds still run.

The feed stays enabled in the dashboard. Hypothesis: AP is blocking the default user agent or that hub URL is no longer a public RSS.

## Paywall mirrors almost never help

**Expected:** When the direct article fetch is thin, archive.is → 1ft.io → archive.org → removepaywall.com recover the text.  
**Actual:** Daily stats show archive.is, 1ft.io, and removepaywall at ~0%. archive.org sometimes recovers a batch (about 14/18 on 30 August). Overall full-text rate is still high because most articles succeed on the first request.

## Books toggle is a text box

**Expected:** `books_delivery_enabled` is a checkbox, like Kindle delivery and the Gmail/Calendar flags.  
**Actual:** The Settings tab renders it as a text field with the string `true`. The `books` group also has no friendly label (it shows as “books”).

Hypothesis: `BOOL_KEYS` and `GROUP_LABELS` in the dashboard script were not updated when the iCloud Books settings were added. Saving the word `true` may still work; saving anything else would not.

## Dashboard reads have no token

**Expected:** On a shared machine, settings are not readable by every local process.  
**Actual:** Write APIs require a Bearer token. `GET /api/settings` and `GET /api/sources` do not. SMTP password is masked on GET; everything else is plaintext on localhost.

This matches the documented single-user threat model. It is still an issue if the Mac is shared.

## Work is not on `main`, and there is no remote

**Expected:** The running digest is the published default branch.  
**Actual:** Useful work is on `main` at [github.com/victor-salles/bitesize](https://github.com/victor-salles/bitesize). Local feature worktrees may still exist; they are not the published default.

## Relevance scores pile up in the same edition

**Expected:** Stories in one digest have a useful spread, so “top stories” are actually the most important ones.  
**Actual (30 Aug 2026):** The most common on-page scores were **7.8, 7.0, and 6.2** — the old length-bucket fallback (78 / 70 / 62) when AI omitted scores or batches failed. That was not the model rating everything equal.

**Belief now:** The August pile was fallback clustering, not proof the AI cannot discriminate. Continuous fallback (capped below 70), tie-spread, and batch-comparative prompting already landed. Task 3 added `relevance_source` (`ai` vs `fallback`) so cover/top picks prefer real AI scores, plus one listwise title-rank pass per batch when AI scores are still too clustered (`unique/n < 0.35`).

**Still open:** Next morning digest should confirm the fallback layer no longer walls at 7.8; listwise un-clustering needs the same real-world check.

## Closed here on purpose (do not re-open from old plans)

These were open in `docs/superpowers/plans/2026-05-26-open-source-security-readiness.md`. The code has moved on:

- Gmail/Calendar are wired into `main.py` (flags still off — that is a roadmap item, not a bug).
- Dashboard writes send `Authorization: Bearer`.
- `dashboard.py` calls `load_env()` on import and always has a write token.
- Partial AI batch JSON no longer drops missing article ids.
- Google OAuth uses combined scopes; calendar “today” uses local time.
- `--dangerously-skip-permissions` is not in the current Antigravity backend.
