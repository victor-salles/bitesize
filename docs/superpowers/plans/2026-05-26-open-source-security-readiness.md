# Open Source Security & Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) / (`- [ ]`) syntax for tracking.

**Goal:** Harden BiteSIze against validated security findings, remove personal/secrets leakage from the repo, and add the standard open-source files and CI checks needed to publish safely.

**Architecture:** Fix concrete medium findings first (EPUB URL escaping, dashboard secret exposure, Wordflow API proxy). Then add repo hygiene (LICENSE, SECURITY.md, redacted docs) and a minimal GitHub Actions workflow running pytest plus secret/dependency scans. Threat model stays **single-user local tool** — dashboard binds to `127.0.0.1`, secrets live in `data/bitesize.db` (gitignored).

**Tech Stack:** Python 3.13, Flask, pytest, Pillow, Next.js (wordflow subproject), GitHub Actions, MIT license.

**Status:** **Implemented on branch `chore/land-session-work`** (51+ commits from `main`). Original review targeted `kindle-epub-opening-layout-694a`; this branch lands OSS hardening plus the full session work (settings DB, dashboard, paywall, magazine EPUB, Antigravity backend, iCloud Books, pt-BR locale).

**Last reviewed:** 2026-08-06 — security-review + Bugbot on `chore/land-session-work` vs `main`.

---

## Original security review findings (baseline — addressed)

| Severity | Location (file:line) | Finding | Status |
|----------|----------------------|---------|--------|
| Medium | `epub.py` (`safe_href`) | Unescaped RSS article URL in EPUB `href` — attribute injection / malicious links | **Fixed** — `safe_href()`, tests in `tests/test_epub_security.py` |
| Medium | `wordflow/app/api/chat/route.ts` | Unauthenticated Anthropic API proxy when app is network-exposed | **Fixed** — localhost guard via `wordflow/lib/requestGuard.ts` |

**Additional scope (required for open source — addressed):**

| Severity | Location | Finding | Status |
|----------|----------|---------|--------|
| Medium | `dashboard.py` | `GET /api/settings` returned `smtp_password` in plaintext JSON | **Fixed** — `settings_for_api(mask_secrets=True)` |
| Low | `dashboard.py` | No auth token — any local process can change settings | **Partial** — optional `DASHBOARD_TOKEN`; see post-review backlog |
| Low | `MOBILE_HANDOFF.md` | Personal email, worker URL, local paths committed | **Fixed** — redacted; `MOBILE_HANDOFF.local.md` gitignored |
| Info | repo root | No `LICENSE`, `SECURITY.md`, or CI | **Fixed** |

---

## Post-implementation review findings (2026-08-06)

### Security review (`chore/land-session-work` vs `main`)

| Severity | Location (file:line) | Finding | Status |
|----------|----------------------|---------|--------|
| Medium | `dashboard.py:22-37` | Write APIs fail-open when `DASHBOARD_TOKEN` unset — local hijack on shared Mac | **Open** — documented threat model; harden in backlog |
| Medium | `antigravity_backend.py:38-52` | `--dangerously-skip-permissions` on untrusted RSS/article text in scheduled digests | **Open** — prompt-injection / agent blast radius |
| — | `epub.py`, `settings_store.py`, `dashboard.py` bind | EPUB XSS, SMTP masking, localhost bind | **Verified OK** |

### Bugbot (`chore/land-session-work` vs `main`)

| Severity | Location (file:line) | Finding | Status |
|----------|----------------------|---------|--------|
| High | `main.py` | Gmail/Calendar integrations never wired into digest pipeline | **Open** — settings exist but RSS-only `main.py` |
| High | `gemini.py:119-140` | Partial AI JSON batch silently drops articles missing from response | **Open** |
| High | `dashboard_static/app.js` | No `Authorization: Bearer` header — UI broken when token set | **Open** |
| Medium | `dashboard.py:17` | `DASHBOARD_TOKEN` read at import; `.env` not loaded via `load_env()` | **Open** |
| Medium | `google_auth.py:11-33` | OAuth `token.json` overwritten per service — combined scopes lost | **Open** (pre-existing) |
| Medium | `calendar_fetch.py:36-63` | “Today” uses UTC midnight, not local TZ | **Open** (pre-existing) |

### Runtime / ops (not in original plan)

| Item | Notes | Status |
|------|-------|--------|
| Antigravity PATH | macOS Shortcuts use minimal `PATH`; `agy` lives in `~/.local/bin` | **Fixed** — `antigravity_backend.py` invokes `~/.local/bin/agy` by full path |
| Paywall mirrors | Fetches archive.is / 1ft.io / archive.org / removepaywall.com | **Shipped** — `paywall.py`; expands untrusted fetch surface (user-controlled feeds) |
| LaunchAgent | `scripts/install-daily-launchd.sh` runs `main.py --all` at 06:50 | **Shipped** — chains with dashboard auth + Antigravity findings |

---

## File map (implemented)

| File | Responsibility |
|------|----------------|
| `epub.py` | `safe_href()`; magazine layout; JPEG cover; pt-BR labels |
| `tests/test_epub_security.py` | URL sanitization TDD |
| `dashboard.py` | Optional token auth; mask secrets on GET |
| `settings_store.py` | SQLite settings; `settings_for_api(mask_secrets=True)` |
| `tests/test_dashboard_api.py` | Auth + secret-masking tests |
| `wordflow/app/api/chat/route.ts` | Localhost guard + message bounds |
| `wordflow/lib/requestGuard.ts` | Shared localhost check (no `middleware.ts` — guard in route + script) |
| `wordflow/scripts/check-chat-guard.mjs` | Manual guard smoke test |
| `MOBILE_HANDOFF.md` | Redacted template |
| `LICENSE` | MIT license |
| `SECURITY.md` | Vulnerability reporting + threat model |
| `CONTRIBUTING.md` | How to run tests, report issues |
| `.github/workflows/ci.yml` | pytest + pip-audit + gitleaks |
| `README.md` | Open-source section, security notes, daily run |
| `.gitignore` | `data/`, `MOBILE_HANDOFF.local.md` |
| `paywall.py` | Archive mirror fallback + stats log |
| `antigravity_backend.py` | `agy` CLI backend; full path to `~/.local/bin/agy` |
| `books.py` | iCloud Books EPUB sync |
| `cover_art.py` / `magazine_layers.py` | Magazine cover and editorial dedup |

---

## Task checklist (original plan)

### Task 1: EPUB external URL sanitization — **DONE**

- [x] `safe_href()` in `epub.py`
- [x] `tests/test_epub_security.py`
- [x] Commit: `Add EPUB safe_href tests` / `Improve EPUB layout and security`

### Task 2: Dashboard secret masking and optional auth token — **DONE (partial)**

- [x] `settings_for_api(mask_secrets=True)`
- [x] `DASHBOARD_TOKEN` on mutating routes
- [x] `dashboard_static/app.js` — omit blank password on save
- [x] `.env.example` documents `DASHBOARD_TOKEN`
- [ ] **Backlog:** `app.js` Bearer header; `dashboard.py` call `load_env()`; fail-closed token default on shared hosts

### Task 3: Wordflow chat API hardening — **DONE**

- [x] `wordflow/lib/requestGuard.ts`
- [x] `wordflow/app/api/chat/route.ts` — localhost + bounds
- [x] `wordflow/scripts/check-chat-guard.mjs`
- [x] `wordflow/README.md`
- Note: `wordflow/middleware.ts` was **not** added; guard lives in route + shared lib (sufficient for local-only default).

### Task 4: Remove personal data from tracked files — **DONE**

- [x] `MOBILE_HANDOFF.md` redacted
- [x] `.gitignore` — `MOBILE_HANDOFF.local.md`, `data/`
- [x] `docs/LOCAL_DEV.md` — generic dev notes

### Task 5: Open-source legal and security docs — **DONE**

- [x] `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`

### Task 6: CI workflow — **DONE**

- [x] `.github/workflows/ci.yml` — pytest, pip-audit, gitleaks

### Task 7: README open-source section — **DONE**

- [x] Open-source + security notes + pre-publish checklist
- [x] Updated again for settings dashboard, Antigravity, paywall, iCloud Books (commit `Update README for current pipeline`)

---

## Backlog (prioritized after 2026-08-06 reviews)

| Priority | Item | Suggested owner |
|----------|------|-----------------|
| P1 | Dashboard `app.js` send `Authorization: Bearer` when token configured | Task 2 follow-up |
| P1 | `dashboard.py` call `load_env()` before reading `DASHBOARD_TOKEN` | Task 2 follow-up |
| P1 | `gemini.py` — keep articles when AI batch JSON omits ids | Bugbot |
| P2 | Wire Gmail/Calendar into `main.py` when integrations enabled | Feature |
| P2 | Remove or gate `--dangerously-skip-permissions` for digest workloads | Security review |
| P2 | Combined Google OAuth scopes in `google_auth.py` | Pre-existing |
| P3 | Calendar “today” in local timezone | Pre-existing |
| P3 | Optional fail-closed dashboard auth on multi-user Macs | Security review |

**Gaps intentionally deferred (original + updated):**

- SSRF hardening for RSS URLs (user-controlled by design for personal digest)
- Full CSRF framework (localhost-only mitigates remote CSRF)
- Dependabot config (add after GitHub repo exists)
- Paywall mirror fetches (user-initiated archive services; same trust as RSS)

---

## Self-review

| Requirement | Original task | Status |
|-------------|---------------|--------|
| EPUB URL injection | 1 | Done |
| Dashboard secret exposure on GET | 2 | Done |
| Wordflow API proxy | 3 | Done |
| Personal data removed | 4 | Done |
| LICENSE / SECURITY / CONTRIBUTING | 5 | Done |
| CI tests + scans | 6 | Done |
| README + publish checklist | 7 | Done |
| TDD where applicable | 1, 2 | Done |
| Dashboard write auth end-to-end | 2 | **Partial** — token + UI gap |
| Gmail/Calendar in pipeline | — | **Not implemented** |
| Antigravity untrusted content | — | **Reviewed** — open |

---

## Execution handoff

**Branch:** `chore/land-session-work` — ready for review/merge to `main` after backlog triage.

**Verify locally:**

```bash
.venv/bin/pytest tests/ -v
pip install pip-audit && pip-audit -r requirements.txt
rg -i 'victor|vsalles@|/Users/victorrodrigues' --glob '!data/**' --glob '!.venv/**'
```

**Next plan (separate):** Hourly article pool + 2×/day digest builder (`docs/superpowers/plans/` — not yet written).
