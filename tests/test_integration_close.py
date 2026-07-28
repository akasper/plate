"""Tests for integration-branch issue close helpers (#427)."""

from __future__ import annotations

import unittest

from plate_core.integration_close import (
    is_integration_branch,
    parse_closing_issue_numbers,
    plan_integration_closes,
    render_close_comment,
    should_auto_close_issue,
)


class TestParseAndBranch(unittest.TestCase):
    def test_integration_branches(self):
        self.assertTrue(is_integration_branch("release"))
        self.assertTrue(is_integration_branch("release-minor"))
        self.assertTrue(is_integration_branch("release-v1.0.0"))
        self.assertTrue(is_integration_branch("refs/heads/release"))
        self.assertTrue(is_integration_branch("epic/foo"))
        self.assertFalse(is_integration_branch("main"))
        self.assertFalse(is_integration_branch("feature/x"))
        self.assertFalse(is_integration_branch(""))

    def test_parse_closing_keywords(self):
        body = "Summary\n\nCloses #488\nFixes #510 and also resolves #508.\n"
        self.assertEqual(parse_closing_issue_numbers(body), [488, 510, 508])
        self.assertEqual(parse_closing_issue_numbers("Related to #99"), [])
        self.assertEqual(
            parse_closing_issue_numbers("Closes https://github.com/a/b/issues/12"),
            [12],
        )


class TestShouldClose(unittest.TestCase):
    def test_skip_epic_task_release(self):
        self.assertFalse(should_auto_close_issue(["Epic", "area:agent"])["close"])
        self.assertFalse(should_auto_close_issue(["Task"])["close"])
        self.assertFalse(should_auto_close_issue(["Release", "Documentation"])["close"])

    def test_close_feature_bug_docs(self):
        self.assertTrue(should_auto_close_issue(["Feature", "area:agent"])["close"])
        self.assertTrue(should_auto_close_issue(["Bug"])["close"])
        self.assertTrue(should_auto_close_issue(["Documentation"])["close"])

    def test_already_closed(self):
        self.assertFalse(should_auto_close_issue(["Feature"], state="closed")["close"])


class TestPlan(unittest.TestCase):
    def test_skip_main(self):
        plan = plan_integration_closes(base_ref="main", pr_body="Closes #1")
        self.assertEqual(plan["action"], "skip")

    def test_plan_close_feature_skip_epic(self):
        plan = plan_integration_closes(
            base_ref="release",
            pr_body="Closes #10\nCloses #20",
            pr_number=99,
            issues=[
                {"number": 10, "state": "open", "labels": ["Feature"]},
                {"number": 20, "state": "open", "labels": ["Epic"]},
            ],
        )
        self.assertEqual(plan["action"], "apply")
        self.assertEqual(plan["to_label"], [10, 20])
        self.assertEqual([c["number"] for c in plan["to_close"]], [10])
        self.assertEqual([s["number"] for s in plan["skipped"]], [20])

    def test_render_comment_has_marker(self):
        text = render_close_comment(pr_number=42, base_ref="release")
        self.assertIn("#42", text)
        self.assertIn("PLATE-INTEGRATION-CLOSE", text)
        self.assertIn("release", text)


if __name__ == "__main__":
    unittest.main()
