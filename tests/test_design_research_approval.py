"""Tests for Design/Research approval surface (#632)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.design_research_approval import (
    artifact_feed_items,
    ask_user_question_payload,
    decide_proposal,
    estimate_artifact_cost,
    get_proposal,
    get_proposal_history,
    list_actionable_proposals,
    list_authoritative,
    list_proposals,
    presentation_for_feed,
    propose_artifact,
    resubmit_proposal,
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
            use_live_budget=False,
        )
        self.assertTrue(out.get("ok", True))
        self.assertTrue(out["id"].startswith("art-"))
        self.assertEqual(out["kind"], "design")
        self.assertEqual(out["status"], "pending")
        self.assertIn("PLATE-ARTIFACT-APPROVAL", out["marker"])
        self.assertIn("ask_user_question", out["prompt_segment"])
        self.assertIn("cost_estimate_tokens", out)
        got = get_proposal(out["id"], base_dir=self.base)
        self.assertEqual(got["related_issue"], 100)

    def test_approve_writes_authoritative(self):
        out = propose_artifact(
            "research",
            "Competitor pricing scan",
            "Summary of 4 competitors",
            content_path="docs/research/pricing.md",
            base_dir=self.base,
            use_live_budget=False,
        )
        decided = decide_proposal(out["id"], "approve", decided_by="human", note="LGTM", base_dir=self.base)
        self.assertTrue(decided["ok"])
        self.assertEqual(decided["status"], "approved")
        auth = list_authoritative(kind="research", base_dir=self.base)
        self.assertEqual(len(auth), 1)
        self.assertTrue(auth[0]["authoritative"])
        self.assertEqual(list_proposals(status="pending", base_dir=self.base), [])

    def test_revise_and_reject(self):
        out = propose_artifact("design", "A", "s", base_dir=self.base, use_live_budget=False)
        rev = decide_proposal(out["id"], "revise", note="needs more detail", base_dir=self.base)
        self.assertEqual(rev["status"], "revised")
        self.assertEqual(rev["version"], 2)
        # revised stays actionable for feed
        actionable = list_actionable_proposals(base_dir=self.base)
        self.assertTrue(any(a["id"] == out["id"] for a in actionable))
        # new proposal then reject
        out2 = propose_artifact("design", "B", "s", base_dir=self.base, use_live_budget=False)
        rej = decide_proposal(out2["id"], "reject", base_dir=self.base)
        self.assertEqual(rej["status"], "rejected")

    def test_resubmit_and_history(self):
        out = propose_artifact(
            "design",
            "Checkout",
            "v1",
            content_path="docs/design/a.md",
            base_dir=self.base,
            use_live_budget=False,
        )
        decide_proposal(out["id"], "revise", note="add mobile", base_dir=self.base)
        hist = get_proposal_history(out["id"], base_dir=self.base)
        self.assertTrue(any(h.get("decision") == "revised" for h in hist))
        re = resubmit_proposal(
            out["id"],
            summary="v2 with mobile",
            content_path="docs/design/a-v2.md",
            actor="agent",
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(re["ok"])
        self.assertEqual(re["status"], "pending")
        self.assertGreaterEqual(re["version"], 3)
        self.assertIn("cost_estimate_tokens", re)
        hist2 = get_proposal_history(out["id"], base_dir=self.base)
        self.assertTrue(any(h.get("decision") == "resubmitted" for h in hist2))
        feed = artifact_feed_items(base_dir=self.base)
        self.assertTrue(any(f["id"] == out["id"] for f in feed))

    def test_list_pending_and_feed_shape(self):
        propose_artifact("design", "D1", "s", base_dir=self.base, use_live_budget=False)
        propose_artifact("research", "R1", "s", base_dir=self.base, use_live_budget=False)
        pending = list_proposals(status="pending", base_dir=self.base)
        self.assertEqual(len(pending), 2)
        feed = presentation_for_feed(pending[0])
        self.assertEqual(feed["item_type"], "artifact_approval")
        self.assertEqual(feed["impact"], "high")
        self.assertIn("ask_user_question", feed)
        self.assertTrue(any(o["id"] == "approve" for o in feed["ask_user_question"]["options"]))
        # revised presentation prioritizes resubmit option
        p = propose_artifact("design", "D2", "s", base_dir=self.base, use_live_budget=False)
        decide_proposal(p["id"], "revise", note="more", base_dir=self.base)
        shaped = presentation_for_feed(get_proposal(p["id"], base_dir=self.base))
        self.assertEqual(shaped["ask_user_question"]["options"][0]["id"], "resubmit")

    def test_ask_user_question_on_propose(self):
        out = propose_artifact(
            "design", "D", "summary", base_dir=self.base, use_live_budget=False
        )
        self.assertIn("ask_user_question", out)
        self.assertEqual(out["ask_user_question"]["item_type"], "artifact_approval")
        payload = ask_user_question_payload(out)
        self.assertIn("Approve design", payload["question"])

    def test_decide_records_ledger_when_available(self):
        out = propose_artifact(
            "research", "R", "s", base_dir=self.base, use_live_budget=False
        )
        # ledger may write to default dir; best-effort field
        decided = decide_proposal(out["id"], "approve", base_dir=self.base)
        self.assertTrue(decided["ok"])
        # ledger_id optional if ledger path fails; still success
        self.assertEqual(decided["status"], "approved")

    def test_budget_gate(self):
        est = estimate_artifact_cost(kind="design")
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        blocked = propose_artifact(
            "design",
            "Too expensive",
            "s",
            base_dir=self.base,
            budget_remaining=10,
            use_live_budget=False,
        )
        self.assertFalse(blocked.get("ok"))
        self.assertTrue(blocked.get("blocked"))
        self.assertIn("budget", blocked.get("error") or "")
        ok = propose_artifact(
            "design",
            "Ok",
            "s",
            base_dir=self.base,
            budget_remaining=est["estimated_tokens"] + 1000,
            use_live_budget=False,
        )
        self.assertTrue(ok.get("ok", True))
        self.assertEqual(ok.get("budget_remaining"), est["estimated_tokens"] + 1000)

    def test_budget_blocks_on_durable_would_pause_risk_off(self):
        """#873: propose_artifact blocks on would_pause even when est < remaining."""
        from unittest.mock import patch

        from plate_core.autonomy import save_budget_spend

        bdir = self.base / "budget"
        today = (
            __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .date()
            .isoformat()
        )
        # remaining=5000, per_cycle=10000 → would_pause; design est=3500 < 5000
        save_budget_spend(
            {
                "date": today,
                "spent_today": 45000,
                "spent_this_cycle": 0,
                "spent_usd_today": 0.0,
            },
            base_dir=bdir,
        )

        class _Cfg:
            autonomy = {
                "enabled": False,
                "risk_tolerance": "off",
                "token_budget": {
                    "daily": 50000,
                    "per_cycle": 10000,
                    "action": "pause",
                },
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            out = propose_artifact(
                "design",
                "Paused rails",
                "summary",
                base_dir=self.base,
                use_live_budget=True,
            )

        self.assertFalse(out.get("ok"), out)
        self.assertTrue(out.get("blocked"))
        self.assertIn("budget", out.get("error") or "")
        self.assertTrue(out.get("would_pause_next_cycle"))
        self.assertEqual(out.get("budget_remaining"), 5000)

    def test_propose_live_budget_isolates_under_base_dir(self):
        from plate_core.autonomy import load_budget_spend

        root_before = int((load_budget_spend() or {}).get("spent_today") or 0)
        out = propose_artifact(
            "design",
            "Isolated charge",
            "summary",
            base_dir=self.base,
            use_live_budget=True,
        )
        self.assertTrue(out.get("ok", True), out)
        self.assertIn("budget_charge", out)
        self.assertTrue((out.get("budget_charge") or {}).get("ok"))
        local = load_budget_spend(base_dir=self.base / "budget")
        self.assertGreater(int(local.get("spent_today") or 0), 0)
        self.assertEqual(
            int((load_budget_spend() or {}).get("spent_today") or 0), root_before
        )


if __name__ == "__main__":
    unittest.main()
