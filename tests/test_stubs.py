"""Tests for stub issue authoring + refinement lifecycle (#637)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from plate_core.stubs import (
    author_stub,
    create_stub_issue,
    detect_issue_type,
    estimate_stub_cost,
    list_stubs,
    refine_stub,
    stubs_feed_items,
)


class TestDetectType(unittest.TestCase):
    def test_keywords(self):
        self.assertEqual(detect_issue_type("fix the broken login bug"), "Bug")
        self.assertEqual(detect_issue_type("research competitor pricing"), "Research")
        self.assertEqual(detect_issue_type("should we adopt X?"), "Question")
        self.assertEqual(detect_issue_type("add marketplace packaging support"), "Feature")
        self.assertEqual(detect_issue_type("roadmap epic for autonomy"), "Epic")
        self.assertEqual(detect_issue_type("anything", hint="Task"), "Task")


class TestAuthorRefine(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_author_labels_and_body(self):
        r = author_stub(
            "Add feed ranking for cost signals",
            issue_type="Feature",
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(r["ok"])
        self.assertIn("cost_estimate_tokens", r)
        d = r["draft"]
        self.assertEqual(d["issue_type"], "Feature")
        self.assertIn("status:stub", d["labels"])
        self.assertIn("need:refinement", d["labels"])
        self.assertIn("Feature", d["labels"])
        self.assertIn("Acceptance criteria", d["body"])
        self.assertTrue(list_stubs(base_dir=self.base))

    def test_refine_and_ready(self):
        r = author_stub(
            "Investigate MCP latency",
            issue_type="Research",
            base_dir=self.base,
            use_live_budget=False,
        )
        did = r["draft"]["id"]
        ref = refine_stub(
            did,
            add_acceptance=["Document method", "Cite sources"],
            answers={"scope": "plate-core only"},
            base_dir=self.base,
        )
        self.assertTrue(ref["ok"])
        self.assertEqual(ref["draft"]["status"], "refining")
        self.assertIn("Document method", ref["draft"]["acceptance_criteria"])
        ready = refine_stub(did, mark_ready=True, base_dir=self.base)
        self.assertEqual(ready["draft"]["status"], "ready")
        self.assertIn("status:ready-to-work", ready["draft"]["labels"])
        self.assertNotIn("status:stub", ready["draft"]["labels"])

    def test_create_dry_run(self):
        r = author_stub(
            "broken CI on labels",
            issue_type="Bug",
            base_dir=self.base,
            use_live_budget=False,
        )
        c = create_stub_issue(
            r["draft"]["id"], dry_run=True, base_dir=self.base, use_live_budget=False
        )
        self.assertTrue(c["ok"])
        self.assertTrue(c["dry_run"])
        self.assertTrue(c["would_create"])
        self.assertIn("Bug", c["labels"])
        self.assertIn("cost_estimate_tokens", c)

    def test_create_apply_mocked(self):
        r = author_stub(
            "design wireframes for feed",
            issue_type="Design",
            base_dir=self.base,
            use_live_budget=False,
        )
        mock = MagicMock()
        mock.api.return_value = {"number": 99, "html_url": "https://example.com/99"}
        c = create_stub_issue(
            r["draft"]["id"],
            dry_run=False,
            client=mock,
            repo="akasper/plate",
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(c["ok"])
        self.assertEqual(c["number"], 99)
        mock.api.assert_called_once()
        updated = list_stubs(status="created", base_dir=self.base)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["github_number"], 99)

    def test_feed(self):
        author_stub(
            "Question about release cadence",
            base_dir=self.base,
            use_live_budget=False,
        )
        feed = stubs_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        self.assertIn("ask_user_question", feed[0])

    def test_budget_gate(self):
        est = estimate_stub_cost(create=False)
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        blocked = author_stub(
            "Add feature under budget",
            base_dir=self.base,
            budget_remaining=10,
            use_live_budget=False,
        )
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked.get("blocked"))
        self.assertIn("budget", blocked.get("error") or "")
        ok = author_stub(
            "Add feature ok",
            base_dir=self.base,
            budget_remaining=est["estimated_tokens"] + 500,
            use_live_budget=False,
        )
        self.assertTrue(ok["ok"])
        c_block = create_stub_issue(
            ok["draft"]["id"],
            dry_run=False,
            budget_remaining=10,
            use_live_budget=False,
            base_dir=self.base,
        )
        self.assertFalse(c_block["ok"])
        self.assertTrue(c_block.get("blocked"))


if __name__ == "__main__":
    unittest.main()
