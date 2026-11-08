---
name: linear-review-inbox
description: Sync with Victor's Linear comments and description edits. Use when looking for how Victor answered, what he changed on Linear issues, or when the user asks what changed in Linear. Do not run automatically at session start. Runs the review-inbox digest instead of opening tickets one by one.
---

# Linear review inbox

Victor answers in Linear by commenting or editing an issue description. Those edits **are** the spec. Status is not the signal.

Do not run this at session start. Run it when you need to know what he said on Linear.

```bash
source .venv/bin/activate
python scripts/linear-review-inbox.py
```

That is the only fetch path. Do not `get_issue` / `list_comments` in a loop to reconstruct this queue. Do not use Linear notifications or Delegate.

Needs Linear credentials in `.env`. Personal API keys are paid-only; on the free plan use the OAuth app’s client id/secret (`LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`) with client-credentials enabled. See `.env.example`.

If the script cannot authenticate, fall back to Linear MCP (`list_issues` with a recent `updatedAt`, then `list_comments` on those issues). Cursor is already signed into Linear.

## How to read the digest

- Current description + new comments **are** the response. Lead with what he decided, not how Linear stored it.
- A missing snapshot (first run) prints recent issues he touched. Later runs print only **new** comments and **changed** descriptions.
- Empty output means do not invent work from stale chat.

## After absorbing

1. Act on the answers. Do not reassign Victor's ticket to Cursor. If execution follows, open a **new** child assigned to Cursor.
2. Leave a short Linear comment if you took an action. Move the ticket on (`Done` when the question is answered).
3. Then record that you saw this inbox:

```bash
python scripts/linear-review-inbox.py --mark-seen
```

The snapshot lives in gitignored `data/linear-review-inbox.json`. It is what stops the next run from treating the same comments as news.
