"""Tests for human/agent co-existence helpers (#643 / #651)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.collab import (
    DRIVER_HUMAN,
    analyze_pr_authorship,
    branch_etiquette_check,
    claim_ownership,
    collab_policy_check,
    collab_status_for_issue,
    concurrent_edit_risk,
    filter_work_for_driver,
    get_driver,
    is_bot_login,
    list_ownership_claims,
    ownership_feed_items,
    release_ownership,
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


class TestOwnership651(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_claim_path_blocks_agent_edit(self):
        r = claim_ownership(
            kind="path",
            target="src/plate_core/collab.py",
            owner="human",
            reason="editing locally",
            base_dir=self.base,
        )
        self.assertTrue(r["ok"])
        cid = r["claim"]["id"]
        g = collab_policy_check(
            "edit_files",
            paths=["src/plate_core/collab.py"],
            base_dir=self.base,
        )
        self.assertFalse(g["allowed"])
        self.assertIn(cid, g.get("claim_ids") or [])
        # child path covered by parent dir claim
        claim_ownership(kind="path", target="src/secrets", owner="human", base_dir=self.base)
        g2 = collab_policy_check(
            "push_branch",
            paths=["src/secrets/keys.env"],
            base_dir=self.base,
        )
        self.assertFalse(g2["allowed"])

    def test_release_and_list(self):
        r = claim_ownership(kind="branch", target="feature/mine", owner="human", base_dir=self.base)
        cid = r["claim"]["id"]
        open_c = list_ownership_claims(base_dir=self.base)
        self.assertEqual(len(open_c), 1)
        rel = release_ownership(cid, base_dir=self.base)
        self.assertTrue(rel["ok"])
        self.assertEqual(list_ownership_claims(base_dir=self.base), [])

    def test_branch_human_claim_blocks_push(self):
        claim_ownership(kind="branch", target="feature/wip", owner="human", base_dir=self.base)
        g = collab_policy_check("push_branch", branch="feature/wip", base_dir=self.base)
        self.assertFalse(g["allowed"])

    def test_etiquette_integration_branch(self):
        e = branch_etiquette_check("release")
        self.assertFalse(e["ok"])
        e2 = branch_etiquette_check(
            "feature/x",
            worktree_root="/tmp/repo",
            repo_root="/tmp/repo",
        )
        self.assertFalse(e2["ok"])
        e3 = branch_etiquette_check(
            "feature/x",
            worktree_root="/tmp/repo-wt",
            repo_root="/tmp/repo",
        )
        self.assertTrue(e3["ok"])

    def test_concurrent_and_feed(self):
        claim_ownership(kind="path", target="docs", owner="human", base_dir=self.base)
        risk = concurrent_edit_risk(["docs/wiki/Goals.md"], base_dir=self.base)
        self.assertEqual(risk["level"], "blocked")
        feed = ownership_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        self.assertEqual(feed[0]["item_type"], "collab_ownership")
        self.assertIn("ask_user_question", feed[0])


if __name__ == "__main__":
    unittest.main()
