# CLAUDE.md

Agent entrypoint for BiteSIze. Humans start at [README.md](README.md). Direction lives in [ROADMAP.md](ROADMAP.md). Known problems live in [ISSUES.md](ISSUES.md).

## Truth hierarchy

| Rank | Source | Use for |
|------|--------|---------|
| 1 | Code + `tests/` | What actually runs |
| 2 | `data/bitesize.db` | Live settings and RSS sources (gitignored) |
| 3 | This file | How to work here |
| 4 | [ISSUES.md](ISSUES.md) / [ROADMAP.md](ROADMAP.md) | Current problems and direction |
| 5 | [README.md](README.md) | Human setup |
| — | `docs/superpowers/plans/` | Historical plans — **check code before treating a finding as open** |

`.env` and `sources.json` are **seed only**. After the first migrate they are not the runtime source of truth.

## Before you change anything

1. Read [ISSUES.md](ISSUES.md) if the work is a bug or a flake.
2. Read [ROADMAP.md](ROADMAP.md) if the work is a feature.
3. Confirm the setting you care about in the dashboard or `data/bitesize.db`, not in `.env`.

## Commands

```bash
source .venv/bin/activate
pytest tests/ -v
python dashboard.py          # http://127.0.0.1:8765
python main.py --all         # full digest
python main.py --all --no-kindle --no-books
```

Write APIs on the dashboard need `Authorization: Bearer <token>`. Token is `DASHBOARD_TOKEN` or `data/dashboard.token` (auto-created). The UI field stores it in localStorage.

Daily run: `scripts/install-daily-launchd.sh` → `main.py --all` at 06:50. Logs: `output/logs/digest-stdout.log`.

## Pipeline

`main.py` is the only orchestrator:

RSS (parallel) → full text + paywall mirrors → AI filter/summarize/score → section + global covers → EPUB → Kindle SMTP → iCloud Books.

Gmail and Calendar inject extra sections when their integration flags are on. The daily LaunchAgent uses `--all`, so it honors those flags from the database and does not prompt.

AI calls go through `ai.py` (`antigravity` / `gemini` / `ollama`). Prompts live in `gemini.py` plus the Gmail/Calendar processors. If the backend is down, the digest still writes: length-based relevance, no summaries.

## Conventions

- **Single-user local tool.** Dashboard binds `127.0.0.1`. Do not expose it.
- **Secrets stay off git:** `.env`, `data/`, `token.json`, `credentials.json`, `output/`.
- **Tests first** for behavior changes. `pytest tests/ -v` is the gate.
- **Delivery is best-effort.** Kindle/Books failures must not abort EPUB write.
- **Stock Kindle has no JavaScript.** Internal links, covers, and reflowable HTML only. See `docs/research/2026-08-14-kindle-interactive-epub.md` before promising interactivity.
- **Tags / completeness / Safari Reader** — tags (`resumo` / `artigo-completo` + pt-BR temas) are in the digest. Safari Reader extract was measured and dropped. See [ROADMAP.md](ROADMAP.md) item 2.
- **`wordflow/`** is a separate experimental Next.js app. Do not treat it as part of the digest unless the task names it.
- **Published default is `main`.** Remote: `https://github.com/victor-salles/bitesize`. Do not commit `.env`, `data/`, or `output/`.
- **Commits, branches and releases** follow `~/.claude/rules/git-conventions.md`: Conventional Commits, `main` as the only long-lived branch, SemVer tags with GitHub Releases (no CHANGELOG file). Use `/personal-commits`, `/personal-pr` and `/personal-release`. Before `v1.0.0` (the "Ready" bar in CONTEXT.md), breaking changes bump MINOR.

## Agent skills

### Issue tracker

GitHub Issues, with planned work on the [BiteSIze Server board](https://github.com/users/victor-salles/projects/3). See `docs/agents/issue-tracker.md`. Victor’s comments and description edits on an issue are his response.

Decisions are recorded as ADRs in `docs/adr/`.

### Triage labels

Default roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root. See `docs/agents/domain.md`.

### Jev + dashboard pattern

Reuse Jev scoring or the Jev review table (including an email client): `docs/agents/jev-ui-handoff.md`.

## Put down

When a run, review, or fix changes what is true, update [ISSUES.md](ISSUES.md) or [ROADMAP.md](ROADMAP.md) in the same change. Do not grow this file with status.
