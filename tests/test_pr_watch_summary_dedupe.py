"""Tests for resolved-comment dedupe in pr_watch_summary (#1096)."""

import tempfile
import unittest
from pathlib import Path

from plate_core.pr_watch_summary import (
    ResolvedLedger,
    build_wake_summary,
    comment_fingerprint,
    is_actionable,
    load_resolved,
    mark_resolved,
    resolved_path,
    save_resolved,
)


def _user(login: str) -> dict:
    return {"login": login}


class TestPrWatchSummaryDedupe(unittest.TestCase):
    def test_suppresses_repeated_resolved_copilot_comment(self):
        comment_a = {
            "user": _user("copilot-pull-request-reviewer[bot]"),
            "body": "Please   update\nthis line.",
            "path": "src/foo.py",
            "line": 3,
        }
        comment_b = {
            "user": _user("copilot-pull-request-reviewer[bot]"),
            "body": "please update this line.",
            "path": "src/foo.py",
            "original_line": 3,
        }
        fingerprint = comment_fingerprint(comment_a)
        self.assertEqual(fingerprint, comment_fingerprint(comment_b))

        delta = {"review_comments": [comment_b], "issue_comments": [], "reviews": []}
        summary = build_wake_summary(
            delta,
            {"head_sha": "a"},
            {"head_sha": "a"},
            resolved=frozenset({fingerprint}),
        )
        self.assertEqual(summary["review_comments"], [])
        self.assertEqual(summary["suppressed_repeats"], 1)
        self.assertFalse(is_actionable(summary))

    def test_new_copilot_comment_remains_actionable(self):
        delta = {
            "review_comments": [
                {
                    "user": _user("copilot-pull-request-reviewer[bot]"),
                    "body": "Please update this line.",
                    "path": "src/foo.py",
                    "line": 3,
                }
            ],
            "issue_comments": [],
            "reviews": [],
        }
        summary = build_wake_summary(delta, {"head_sha": "a"}, {"head_sha": "a"})
        self.assertEqual(len(summary["review_comments"]), 1)
        self.assertEqual(summary["suppressed_repeats"], 0)
        self.assertTrue(is_actionable(summary))

    def test_resolved_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = resolved_path("acme/widget", 42, root=root)
            self.assertEqual(
                path,
                root / ".agentic" / "babysit" / "acme-widget-42.resolved.json",
            )
            ledger = ResolvedLedger()
            comment = {
                "path": "src/a.py",
                "line": 1,
                "body": "fix me",
            }
            mark_resolved(ledger, [comment])
            save_resolved(path, ledger)
            loaded = load_resolved(path)
            self.assertEqual(loaded.fingerprints, ledger.fingerprints)

    def test_build_wake_summary_without_resolved_unchanged(self):
        delta = {
            "issue_comments": [
                {"user": _user("alice"), "body": "please fix", "html_url": "u4"},
            ],
            "review_comments": [],
            "reviews": [],
        }
        summary = build_wake_summary(
            delta,
            {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
            {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
        )
        self.assertEqual(len(summary["issue_comments"]), 1)
        self.assertEqual(summary["suppressed_repeats"], 0)
        self.assertTrue(is_actionable(summary))


if __name__ == "__main__":
    unittest.main()
