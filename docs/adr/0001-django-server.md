# 1. Multi-user server in Django

- **Status:** accepted
- **Date:** 2026-11-13
- **Issue:** [#53](https://github.com/victor-salles/bitesize/issues/53) · Board: [BiteSIze Server](https://github.com/users/victor-salles/projects/3)

## Context

BiteSIze is a single-user tool. It runs on Victor's Mac, keeps its settings in `data/bitesize.db`, and serves a dashboard bound to `127.0.0.1`. Victor wants friends to use it too: each with an account, their own news sources and their own Kindle, and with everything — sign-up, sources, delivery — done from the Kindle's browser.

The pipeline itself (RSS → full text → AI → EPUB → Kindle email) is tested and works. What is missing is accounts, per-user settings, a queue and a server to run on.

## Decision

Build a Django server that wraps the existing pipeline. Do not rewrite the pipeline.

| Concern | Choice | Why |
|---|---|---|
| Framework | Django 6 | Accounts, sessions, forms, admin and migrations come built in. |
| Pipeline | Existing code as a package called once per user ([#55](https://github.com/victor-salles/bitesize/issues/55)) | Keeps the tested code; the server only supplies each user's inputs. |
| Interface | Server-rendered templates and plain forms, no JavaScript dependency | The Kindle browser is the main client. Monochrome, high-contrast design ([#58](https://github.com/victor-salles/bitesize/issues/58)). |
| API | None for now; no Django REST Framework | Nothing consumes an API yet. Add DRF when something does. |
| Login | Name + short PIN, long-lived session | Typing a password on the Kindle keyboard is painful, and the Kindle has no mail app for magic links. |
| Database | SQLite on a persistent volume | Friends-sized load; saves RAM on the 1 GB droplet. |
| Background work | Django's built-in tasks with the `django-tasks-db` database backend, one worker, one edition at a time | Fits the droplet's memory. Users see their place in the queue and the expected wait ([#64](https://github.com/victor-salles/bitesize/issues/64)). |
| Scheduling | A management command run by Dokku cron enqueues due users | Django has no scheduler of its own. |
| AI | Gemini with the server's key; summaries cached per article | A story followed by several users is processed once. |
| Email | A transactional provider sending from `victorsalles.com` | Gmail SMTP limits and deliverability. Each user approves the sender once in Amazon, guided by the app ([#60](https://github.com/victor-salles/bitesize/issues/60)). |
| Hosting | Dokku app `bitesize` at `bitesize.victorsalles.com` | Same setup as Victor's other personal apps. |

## Out of scope for the server

- iCloud Books delivery (macOS only).
- Gmail and Calendar sections (each friend would need Google OAuth). Possible later.
- Antigravity and Ollama backends.

## Consequences

- The local CLI and dashboard keep working while the server is built. Whether they stay after the server ships is a later decision.
- `CLAUDE.md`'s "single-user local tool, do not expose the dashboard" rule still holds for the local dashboard. The server is a separate app with its own auth.
- Server features ship as MINOR releases before `v1.0.0`; the first is planned as `v0.2.0`.
