# Issue tracker: GitHub

Issues live in GitHub Issues on [victor-salles/bitesize](https://github.com/victor-salles/bitesize/issues). Planned work is on the [BiteSIze Server](https://github.com/users/victor-salles/projects/3) project board. Use the `gh` CLI.

Linear was the tracker until 2026-11-13. Old `VIC-*` links in the docs still point there; do not open new Linear tickets.

## Conventions

- **Create:** `gh issue create --repo victor-salles/bitesize --title … --body-file … --label <triage label>`, then add it to the board: `gh project item-add 3 --owner victor-salles --url <issue url>`. Use a milestone when the work belongs to one (e.g. `Server MVP`).
- **Read:** `gh issue view <number> --comments`.
- **List:** `gh issue list --label ready-for-agent` for the agent queue, `--label ready-for-human` for Victor's.
- **Comment:** `gh issue comment <number> --body-file …`.
- **Labels:** `gh issue edit <number> --add-label … --remove-label …`.
- **Close:** a PR with `Closes #<number>` closes it on merge. Close by hand only for won't-fix or duplicates.

## Who owns what

**One issue, one owner**, shown by the triage label.

| Label | Owner | Covers |
|---|---|---|
| `ready-for-human` | Victor | Decisions, design, review, releases. |
| `ready-for-agent` | Agent | Research, tasks, implementation. |

If an issue needs a human answer before agent work, keep the question on Victor's issue and open a new `ready-for-agent` issue once the answer exists.

## Review handshake

Victor's answer is a **comment or a description edit** on the issue. Read those as the spec: `gh issue view <number> --comments`.

## Writing

Issue bodies follow writing-around-code: lead with the problem or decision in plain language and end with a **Done when** line. Name files only when they earn their place.

## Pull requests

- Branch, commit and PR-title rules are in [CONTRIBUTING.md](../../CONTRIBUTING.md).
- The PR body says `Closes #<number>`.
- PRs are not a place to request new work; open an issue.

## When a skill says "publish to the issue tracker"

Create a GitHub issue as above.

## When a skill says "fetch the relevant ticket"

`gh issue view` on the number or URL the user passed.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue labelled `wayfinder:map`; tickets are its sub-issues.

- **Child ticket:** create the issue, then link it as a sub-issue of the map (`gh api` on the sub-issues endpoint), labelled `wayfinder:<type>` plus a triage label.
- **Blocking:** write `Blocked by #<n>` in the body. A ticket is unblocked when every blocker is closed.
- **Frontier for agents:** the map's open `ready-for-agent` children with no open blocker; first in map order wins.
- **Resolve:** comment with the answer, close the issue, and add a pointer to the map's Decisions-so-far.
