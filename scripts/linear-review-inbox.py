"""Pull issues Victor commented on or whose description he edited.

One GraphQL call for recently updated issues, then keep only his activity.
Compare against a gitignored snapshot so a later run only highlights new
comments and changed descriptions.

Usage:
    python scripts/linear-review-inbox.py
    python scripts/linear-review-inbox.py --mark-seen
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / "data" / "linear-review-inbox.json"
ENV_FILE = ROOT / ".env"
GRAPHQL_URL = "https://api.linear.app/graphql"
TOKEN_URL = "https://api.linear.app/oauth/token"
ACTOR_NAME = "Victor Salles"
LOOKBACK_DAYS = 14

INBOX_QUERY = """
query ReviewInbox($since: DateTime!) {
  issues(
    first: 50
    orderBy: updatedAt
    filter: {
      updatedAt: { gte: $since }
    }
  ) {
    nodes {
      identifier
      title
      url
      description
      updatedAt
      comments(first: 100) {
        nodes {
          id
          body
          createdAt
          user { name }
        }
      }
      history(first: 20, orderBy: updatedAt) {
        nodes {
          createdAt
          updatedDescription
          actor { name }
          fromState { name }
          toState { name }
        }
      }
    }
  }
}
"""


def description_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def issues_from_graphql(payload: dict) -> list[dict]:
    nodes = (((payload or {}).get("data") or {}).get("issues") or {}).get("nodes") or []
    issues = []
    for node in nodes:
        comments = []
        for raw in ((node.get("comments") or {}).get("nodes") or []):
            user = raw.get("user") or {}
            author = user.get("name") or "unknown"
            if author != ACTOR_NAME:
                continue
            comments.append(
                {
                    "id": raw["id"],
                    "body": raw.get("body") or "",
                    "createdAt": raw.get("createdAt") or "",
                    "author": author,
                }
            )
        comments.sort(key=lambda c: (c["createdAt"], c["id"]))
        history = (node.get("history") or {}).get("nodes") or []
        description_edited = any(
            h.get("updatedDescription") and ((h.get("actor") or {}).get("name") == ACTOR_NAME)
            for h in history
        )
        issues.append(
            {
                "identifier": node["identifier"],
                "title": node.get("title") or "",
                "url": node.get("url") or "",
                "description": node.get("description") or "",
                "updatedAt": node.get("updatedAt") or "",
                "comments": comments,
                "description_edited": description_edited,
            }
        )
    return issues


def build_snapshot(issues: list[dict]) -> dict:
    return {
        "issues": {
            issue["identifier"]: {
                "description_hash": description_hash(issue["description"]),
                "comment_ids": [c["id"] for c in issue["comments"]],
            }
            for issue in issues
            if issue["comments"] or issue["description_edited"]
        }
    }


def load_snapshot(path: Path) -> dict:
    if not path.is_file():
        return {"issues": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "issues" not in data:
        return {"issues": {}}
    return data


def save_snapshot(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


def _issue_delta(issue: dict, prev: dict | None) -> tuple[bool, list[dict]]:
    """Return (show_description, new_comments). prev is None on a first look."""
    if prev is None:
        if not issue["comments"] and not issue["description_edited"]:
            return False, []
        return True, list(issue["comments"])
    desc_changed = prev.get("description_hash") != description_hash(issue["description"])
    seen_ids = set(prev.get("comment_ids") or [])
    new_comments = [c for c in issue["comments"] if c["id"] not in seen_ids]
    return desc_changed, new_comments


def format_digest(issues: list[dict], seen: dict | None) -> str:
    empty = f"No comments or description edits from {ACTOR_NAME}.\n"
    if not issues:
        return empty

    seen_map = None if seen is None else (seen.get("issues") or {})
    sections = []
    for issue in issues:
        prev = None if seen_map is None else seen_map.get(issue["identifier"])
        show_description, new_comments = _issue_delta(issue, prev)
        if not show_description and not new_comments:
            continue
        lines = [
            f"## {issue['identifier']} — {issue['title']}",
            issue["url"],
            "",
        ]
        if show_description:
            lines.extend(["### Description", issue["description"].rstrip(), ""])
        if new_comments:
            lines.append("### New comments")
            for comment in new_comments:
                author = comment["author"]
                when = comment["createdAt"]
                body = comment["body"].rstrip()
                lines.append(f"- {when} {author}:")
                lines.append(f"  {body}")
            lines.append("")
        sections.append("\n".join(lines).rstrip())

    if not sections:
        if seen is None:
            return empty
        return f"No new comments or description edits from {ACTOR_NAME}.\n"

    header = f"# Linear review inbox\n\nComments and description edits by {ACTOR_NAME}.\n"
    return header + "\n\n".join(sections) + "\n"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip().strip("'").strip('"')
    return values


def env_get(name: str) -> str:
    return os.environ.get(name, "").strip() or _parse_env_file(ENV_FILE).get(name, "")


def authorization_header(token: str) -> str:
    if token.startswith("lin_api_") or token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def request_client_credentials_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "scope": "read",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    payload = {}
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        detail = payload.get("error_description") or payload.get("error") or response.text
        raise RuntimeError(f"OAuth client_credentials failed: {detail}")
    token = payload.get("access_token") or ""
    if not token:
        raise RuntimeError("OAuth client_credentials returned no access_token")
    return token


def load_token() -> str:
    for name in ("LINEAR_API_KEY", "LINEAR_ACCESS_TOKEN"):
        value = env_get(name)
        if value:
            return value
    client_id = env_get("LINEAR_CLIENT_ID")
    client_secret = env_get("LINEAR_CLIENT_SECRET")
    if client_id and client_secret:
        return request_client_credentials_token(client_id, client_secret)
    return ""


def load_api_key() -> str:
    return load_token()


def default_since() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


def fetch_inbox(api_key: str, since: str | None = None) -> dict:
    response = requests.post(
        GRAPHQL_URL,
        json={"query": INBOX_QUERY, "variables": {"since": since or default_since()}},
        headers={
            "Authorization": authorization_header(api_key),
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload


MISSING_CREDS = """No Linear credentials in .env. Personal API keys are not available on the free plan.

Use the OAuth app you already created:
  1. Linear → Settings → Administration → API → your OAuth app
  2. Enable "Client credentials tokens"
  3. Put LINEAR_CLIENT_ID and LINEAR_CLIENT_SECRET in .env
The digest fetches a short-lived token each run.

In Cursor, Linear MCP is already signed in — the agent can still read your comments without this script."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Digest Victor's Linear comments and description edits."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="Path to the last-seen snapshot (default: data/linear-review-inbox.json)",
    )
    parser.add_argument(
        "--mark-seen",
        action="store_true",
        help="Write the current inbox into the snapshot after printing the digest",
    )
    args = parser.parse_args(argv)

    try:
        token = load_token()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print(
            "If that error mentions client_credentials, enable it on the OAuth app.",
            file=sys.stderr,
        )
        return 1
    if not token:
        print(MISSING_CREDS, file=sys.stderr)
        return 1

    seen = load_snapshot(args.snapshot) if args.snapshot.is_file() else None
    since = (seen or {}).get("fetched_at") or default_since()
    payload = fetch_inbox(token, since=since)
    issues = issues_from_graphql(payload)
    sys.stdout.write(format_digest(issues, seen=seen))
    if args.mark_seen:
        snapshot = build_snapshot(issues)
        snapshot["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        save_snapshot(args.snapshot, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
