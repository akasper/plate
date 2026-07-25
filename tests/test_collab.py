"""Tests for human/agent co-existence helpers (#643)."""

from __future__ import annotations

import unittest

from plate_core.collab import (
    DRIVER_HUMAN,
    analyze_pr_authorship,
    collab_policy_check,
    collab_status_for_issue,
    filter_work_for_driver,
    get_driver,
    is_bot_login,
    should_pause_delegation,
    should_prefer_human_review,
)


class TestDriverLabels(unittest.TestCase):
    def test_driver_modes(self):
        self.assertEqual(get_driver([DRIVER_HUMAN]), "human")
        self.assertEqual(get_driver(["driver:collaborative"]), "collaborative")
        self.assertEqual(get_driver(["Feature"]), "agent")
        self.assertTrue(should_pause_delegation([DRIVER_HUMAN]))
        self.assertFalse(should_pause_delegation(["driver:agent"]))
        self.assertTrue(should_prefer_human_review(["need:human-review"]))


class TestAuthorship(unittest.TestCase):
    def test_bot_login(self):
        self.assertTrue(is_bot_login("dependabot[bot]"))
        self.assertTrue(is_bot_login("copilot-swe-agent"))
        self.assertFalse(is_bot_login("akasper"))

    def test_mixed_commits(self):
        rep = analyze_pr_authorship(
            pr_number=1,
            author_login="copilot[bot]",
            commits=[
                {"author": {"login": "akasper"}},
                {"author": {"login": "dependabot[bot]"}},
            ],
        )
        self.assertEqual(rep.mix, "mixed")
        self.assertEqual(rep.human_commits, 1)
        self.assertEqual(rep.bot_commits, 1)
        self.assertTrue(rep.notes)


class TestPolicy(unittest.TestCase):
    def test_force_push_blocked_on_mixed(self):
        auth = analyze_pr_authorship(
            commits=[
                {"author": {"login": "human1"}},
                {"author": {"login": "bot[bot]"}},
            ]
        )
        g = collab_policy_check("force_push", authorship=auth)
        self.assertFalse(g["allowed"])
        self.assertTrue(g["escalate"])

    def test_driver_human_blocks_delegate(self):
        g = collab_policy_check("delegate", labels=[DRIVER_HUMAN])
        self.assertFalse(g["allowed"])

    def test_agent_driver_allows_push(self):
        g = collab_policy_check("push_branch", labels=["driver:agent"])
        self.assertTrue(g["allowed"])

    def test_filter_work(self):
        items = [
            {"id": "1", "labels": [DRIVER_HUMAN], "title": "H"},
            {"id": "2", "labels": ["Feature"], "title": "A"},
        ]
        out = filter_work_for_driver(items)
        self.assertEqual(out["n_paused"], 1)
        self.assertEqual(out["n_assignable"], 1)
        self.assertEqual(out["assignable"][0]["id"], "2")

    def test_issue_status(self):
        st = collab_status_for_issue(
            {"number": 9, "title": "X", "labels": [{"name": DRIVER_HUMAN}]}
        )
        self.assertEqual(st["driver"], "human")
        self.assertTrue(st["pause_delegation"])
        self.assertIn("PLATE-COLLAB", st["marker"])


if __name__ == "__main__":
    unittest.main()
