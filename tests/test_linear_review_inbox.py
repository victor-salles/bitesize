"""Digest of Victor's Linear comments and description edits — no live API."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "linear-review-inbox.py"


def load_inbox():
    spec = importlib.util.spec_from_file_location("linear_review_inbox", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def issue_node(
    identifier,
    title,
    description="Question body",
    comments=None,
    description_edited=False,
):
    history = []
    if description_edited:
        history.append(
            {
                "createdAt": "2026-09-07T01:33:00.000Z",
                "updatedDescription": True,
                "actor": {"name": "Victor Salles"},
                "fromState": {"name": "Todo"},
                "toState": {"name": "In Review"},
            }
        )
    return {
        "identifier": identifier,
        "title": title,
        "url": f"https://linear.app/victor-salles/issue/{identifier}/slug",
        "description": description,
        "updatedAt": "2026-09-07T01:33:00.000Z",
        "comments": {"nodes": comments or []},
        "history": {"nodes": history},
    }


def comment(cid, body, created="2026-09-07T01:25:20.271Z", author="Victor Salles"):
    return {
        "id": cid,
        "body": body,
        "createdAt": created,
        "user": {"name": author},
    }


def two_issue_payload(extra_comment=None):
    comments_10 = [comment("c-nyt", "Nyt, Wired and BBC")]
    if extra_comment:
        comments_10.append(extra_comment)
    return {
        "data": {
            "issues": {
                "nodes": [
                    issue_node(
                        "VIC-10",
                        "Generic seed feeds for a fresh clone",
                        description="Which public feeds should a fresh clone start with?",
                        comments=comments_10,
                    ),
                    issue_node(
                        "VIC-12",
                        "README screenshot set",
                        description="Which screenshots, in which order?",
                        comments=[
                            comment(
                                "c-shot",
                                "just that one, homepage. later I'll add a screenshot of the Kindle cover",
                                created="2026-09-07T01:33:05.680Z",
                            )
                        ],
                    ),
                ]
            }
        }
    }


def test_first_digest_lists_issues_victor_touched():
    inbox = load_inbox()
    issues = inbox.issues_from_graphql(two_issue_payload())
    text = inbox.format_digest(issues, seen=None)

    assert "VIC-10" in text
    assert "VIC-12" in text
    assert "Nyt, Wired and BBC" in text
    assert "just that one, homepage" in text
    assert "Which public feeds should a fresh clone start with?" in text


def test_second_digest_with_same_snapshot_prints_nothing_new():
    inbox = load_inbox()
    issues = inbox.issues_from_graphql(two_issue_payload())
    seen = inbox.build_snapshot(issues)
    text = inbox.format_digest(issues, seen=seen)

    assert "VIC-10" not in text
    assert "VIC-12" not in text
    assert "No new comments or description edits" in text


def test_new_comment_appears_as_delta():
    inbox = load_inbox()
    first = inbox.issues_from_graphql(two_issue_payload())
    seen = inbox.build_snapshot(first)
    second = inbox.issues_from_graphql(
        two_issue_payload(
            extra_comment=comment("c-count", "Three feeds is enough.", created="2026-09-07T02:00:00.000Z")
        )
    )
    text = inbox.format_digest(second, seen=seen)

    assert "VIC-10" in text
    assert "Three feeds is enough." in text
    assert "Nyt, Wired and BBC" not in text
    assert "VIC-12" not in text


def test_changed_description_appears_as_delta():
    inbox = load_inbox()
    first = inbox.issues_from_graphql(two_issue_payload())
    seen = inbox.build_snapshot(first)
    payload = two_issue_payload()
    payload["data"]["issues"]["nodes"][1]["description"] = "Homepage only. Kindle shots later."
    second = inbox.issues_from_graphql(payload)
    text = inbox.format_digest(second, seen=seen)

    assert "VIC-12" in text
    assert "Homepage only. Kindle shots later." in text
    assert "VIC-10" not in text


def test_empty_inbox_says_so():
    inbox = load_inbox()
    issues = inbox.issues_from_graphql({"data": {"issues": {"nodes": []}}})
    text = inbox.format_digest(issues, seen=None)
    assert "No comments or description edits" in text


def test_other_people_comments_are_not_victor_activity():
    inbox = load_inbox()
    payload = {
        "data": {
            "issues": {
                "nodes": [
                    issue_node(
                        "VIC-99",
                        "Cursor-only note",
                        comments=[comment("c-bot", "Claimed.", author="Cursor")],
                    )
                ]
            }
        }
    }
    issues = inbox.issues_from_graphql(payload)
    text = inbox.format_digest(issues, seen=None)
    assert "VIC-99" not in text
    assert "No comments or description edits" in text


def test_description_edit_without_comment_counts_as_activity():
    inbox = load_inbox()
    payload = {
        "data": {
            "issues": {
                "nodes": [
                    issue_node(
                        "VIC-9",
                        "Confirm the published-tree keep/drop list",
                        description="Gmail and Calendar stay as Linear backlog.",
                        description_edited=True,
                    )
                ]
            }
        }
    }
    issues = inbox.issues_from_graphql(payload)
    text = inbox.format_digest(issues, seen=None)
    assert "VIC-9" in text
    assert "Gmail and Calendar stay as Linear backlog." in text


def test_mark_seen_writes_snapshot(tmp_path, monkeypatch):
    inbox = load_inbox()
    payload = two_issue_payload()
    snapshot_path = tmp_path / "seen.json"
    monkeypatch.setattr(inbox, "fetch_inbox", lambda api_key, since=None: payload)
    monkeypatch.setattr(inbox, "load_token", lambda: "lin_api_test")
    code = inbox.main(["--snapshot", str(snapshot_path), "--mark-seen"])
    assert code == 0
    assert snapshot_path.is_file()
    seen = inbox.load_snapshot(snapshot_path)
    issues = inbox.issues_from_graphql(payload)
    assert seen["issues"] == inbox.build_snapshot(issues)["issues"]
    assert "fetched_at" in seen


def test_oauth_access_token_uses_bearer_header():
    inbox = load_inbox()
    assert inbox.authorization_header("abc123def") == "Bearer abc123def"
    assert inbox.authorization_header("lin_api_secret") == "lin_api_secret"


def test_load_token_uses_oauth_client_credentials(monkeypatch, tmp_path):
    inbox = load_inbox()
    monkeypatch.setattr(inbox, "ENV_FILE", tmp_path / "missing.env")
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.delenv("LINEAR_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("LINEAR_CLIENT_ID", "cid")
    monkeypatch.setenv("LINEAR_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(
        inbox, "request_client_credentials_token", lambda client_id, client_secret: "oauth-access"
    )
    assert inbox.load_token() == "oauth-access"
