"""Tests for Design/Research approval surface (#632)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.design_research_approval import (
    decide_proposal,
    get_proposal,
    list_authoritative,
    list_proposals,
    presentation_for_feed,
    propose_artifact,
)


class TestDesignResearchApproval632(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "approvals"
        self.base.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_propose_design(self):
        out = propose_artifact(
            "design",
            "Checkout redesign wireframe",
            "3-step checkout with progress bar",
            content_path="docs/design/checkout.md",
            related_issue=100,
            originating_question=50,
            media_links=["https://example.com/wire.png"],
            base_dir=self.base,
        )
        self.assertTrue(out["id"].startswith("art-"))
        self.assertEqual(out["kind"], "design")
        self.assertEqual(out["status"], "pending")
        self.assertIn("PLATE-ARTIFACT-APPROVAL", out["marker"])
        self.assertIn("ask_user_question", out["prompt_segment"])
        got = get_proposal(out["id"], base_dir=self.base)
        self.assertEqual(got["related_issue"], 100)

    def test_approve_writes_authoritative(self):
        out = propose_artifact(
            "research",
            "Competitor pricing scan",
            "Summary of 4 competitors",
            content_path="docs/research/pricing.md",
            base_dir=self.base,
        )
        decided = decide_proposal(out["id"], "approve", decided_by="human", note="LGTM", base_dir=self.base)
        self.assertTrue(decided["ok"])
        self.assertEqual(decided["status"], "approved")
        auth = list_authoritative(kind="research", base_dir=self.base)
        self.assertEqual(len(auth), 1)
        self.assertTrue(auth[0]["authoritative"])
        self.assertEqual(list_proposals(status="pending", base_dir=self.base), [])

    def test_revise_and_reject(self):
        out = propose_artifact("design", "A", "s", base_dir=self.base)
        rev = decide_proposal(out["id"], "revise", note="needs more detail", base_dir=self.base)
        self.assertEqual(rev["status"], "revised")
        self.assertEqual(rev["version"], 2)
        # new proposal then reject
        out2 = propose_artifact("design", "B", "s", base_dir=self.base)
        rej = decide_proposal(out2["id"], "reject", base_dir=self.base)
        self.assertEqual(rej["status"], "rejected")

    def test_list_pending_and_feed_shape(self):
        propose_artifact("design", "D1", "s", base_dir=self.base)
        propose_artifact("research", "R1", "s", base_dir=self.base)
        pending = list_proposals(status="pending", base_dir=self.base)
        self.assertEqual(len(pending), 2)
        feed = presentation_for_feed(pending[0])
        self.assertEqual(feed["item_type"], "artifact_approval")
        self.assertEqual(feed["impact"], "high")


if __name__ == "__main__":
    unittest.main()
