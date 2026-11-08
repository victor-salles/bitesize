# Issue tracker: Linear

Issues and specs for this repo live in Linear. Workspace: [Victor Salles](https://linear.app/victor-salles). Team: **Victor Salles**. Use the Linear MCP (`save_issue`, `get_issue`, `list_issues`, `save_comment`) for all operations.

## Conventions

- **Create an issue**: `save_issue` with `team` = `Victor Salles`, a title, a markdown description, and an **assignee** (see below). Do not escape newlines.
- **Read an issue**: `get_issue` with the identifier (e.g. `VIC-12`).
- **List issues**: `list_issues`, scoped with `team` and labels. Victor’s queue is `assignee` = `Victor Salles`. Cursor’s queue is `assignee` = `Cursor`. Do not use `me` — it follows whoever is logged into Linear, so it mixes the two queues.
- **Comment**: `save_comment` with `issueId` and `body`.
- **Apply / remove labels**: `save_issue` `addLabels` / `removeLabels`. Replacing the full set uses `labels`.
- **Close**: `save_issue` with `state` = `Done`.

## Assignee

**One ticket, one owner.** Assignee is how Victor’s work and Cursor’s work stay on separate lists. Do not put a decision and an implementation on the same issue.

| Assignee | Owns |
| --- | --- |
| `Victor Salles` | Decisions, grilling, review, and anything labelled `ready-for-human`. The map issue itself. |
| `Cursor` | Research, tasks, and execution labelled `ready-for-agent`. |

If a ticket needs both a human answer and later agent work, keep the question on Victor’s issue and open a **new** child assigned to Cursor once the answer exists. Do not reassign Victor’s ticket to Cursor to “start coding.” Do not use Linear’s Delegate field for this split.

Infer the workspace from the connected Linear MCP; do not switch teams unless the user names another one.

## Review handshake

Victor’s response is a **comment or a description edit** on a Linear issue, not chat and not a status. Read those as the spec.

When you need to know what he said, run `python scripts/linear-review-inbox.py` if `.env` has OAuth client credentials (see `.cursor/skills/linear-review-inbox/SKILL.md`). Do not run it automatically at session start. If the script has no credentials, use Linear MCP instead — Cursor is already signed in. After absorbing, `--mark-seen` when the script was used, comment if you acted, and move the ticket on (`Done` when the question is answered).

## Writing

Issue bodies follow writing-around-code: lead with the problem or decision in plain language. The code already holds the mechanics. Name files only when they earn their place. Wayfinder tickets still carry a **Question** (and an **Answer** when resolved); those sections are prose, not a task list.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## When a skill says "publish to the issue tracker"

Create a Linear issue on team Victor Salles.

## When a skill says "fetch the relevant ticket"

`get_issue` on the identifier or URL the user passed.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single Linear issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. Create with `save_issue`, `assignee: "Victor Salles"`, and `addLabels: ["wayfinder:map"]`.
- **Child ticket**: `save_issue` with `parentId` set to the map’s identifier, plus labels `wayfinder:<type>` (`research` / `prototype` / `grilling` / `task`), and an assignee from the table above. Grilling and `ready-for-human` go to Victor Salles. Research, tasks, and agent execution go to Cursor.
- **Blocking**: Linear’s native `blockedBy` / `blocks` on `save_issue`. A ticket is unblocked when every blocker is **Done**.
- **Frontier for Cursor**: the map’s open children assigned to **Cursor** that have no open blocker; first in map order wins. Victor’s tickets are not the agent frontier even if they are unblocked.
- **Claim (Cursor)**: the ticket is already assigned to Cursor; set `state: "In Progress"`. Do not steal a Victor Salles ticket by reassigning it.
- **Resolve**: `save_comment` with the answer, `state: "Done"`, then append a context pointer (gist + Linear URL) to the map’s Decisions-so-far.
