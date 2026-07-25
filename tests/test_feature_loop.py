"""Tests for autonomous feature implementation loop (#639)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.feature_loop import (
    advance_feature_loop,
    assess_human_required,
    cancel_feature_loop,
    estimate_feature_cost,
    feature_loop_feed_items,
    list_feature_loops,
    next_stage,
    run_feature_loop_tick,
    start_feature_loop,
)
from plate_core.feature_loop import update_feature_loop


class TestEstimateAndStages(unittest.TestCase):
    def test_estimate_grows_with_options(self):
        base = estimate_feature_cost(size="small")
        rich = estimate_feature_cost(
            size="small", needs_design_validation=True, needs_media=True, e2e=True
        )
        self.assertGreater(rich["estimated_tokens"], base["estimated_tokens"])

    def test_next_stage_skips(self):
        self.assertEqual(next_stage("estimate_cost"), "plan")
        self.assertEqual(next_stage("docs_fragment", skip_media=True), "ready_for_review")
        self.assertEqual(next_stage("babysit", skip_checkpoint=True), "merge_eligible")


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_start_has_estimate(self):
        r = start_feature_loop(
            feature_number=10,
            feature_title="Feed ranking",
            size="medium",
            risk="low",
            needs_media_approval=False,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["run"]["stage"], "estimate_cost")
        self.assertIsNotNone(r["run"]["cost_estimate_tokens"])
        self.assertIn("estimate", r)

    def test_budget_blocks(self):
        r = start_feature_loop(
            feature_number=11,
            feature_title="Huge",
            size="large",
            budget_remaining=100,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["blocked"])
        self.assertEqual(r["run"]["status"], "blocked")

    def test_advance_low_risk_to_done(self):
        r = start_feature_loop(
            feature_number=12,
            feature_title="Tiny",
            size="trivial",
            risk="low",
            needs_media_approval=False,
            risk_tolerance="high",
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        stage = r["run"]["stage"]
        for _ in range(15):
            out = advance_feature_loop(rid, skip_media=True, base_dir=self.base)
            self.assertTrue(out["ok"])
            if not out.get("advanced"):
                break
            stage = out["to_stage"]
            if stage == "done":
                break
        self.assertEqual(stage, "done")

    def test_babysit_gate(self):
        r = start_feature_loop(
            feature_number=13,
            feature_title="g",
            pr_number=5,
            needs_media_approval=False,
            risk="low",
            risk_tolerance="high",
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        self.assertEqual(r["run"]["stage"], "babysit")
        blocked = advance_feature_loop(
            rid, gates={"merge_state": "BEHIND", "unresolved_review_threads": 0}, base_dir=self.base
        )
        self.assertFalse(blocked["advanced"])
        ok = advance_feature_loop(
            rid, gates={"merge_state": "CLEAN", "unresolved_review_threads": 0}, base_dir=self.base
        )
        self.assertTrue(ok["advanced"])

    def test_babysit_blocks_on_ci_failing(self):
        r = start_feature_loop(
            feature_number=15,
            feature_title="ci gate",
            pr_number=6,
            needs_media_approval=False,
            risk="low",
            risk_tolerance="high",
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        blocked = advance_feature_loop(
            rid,
            gates={
                "merge_state": "CLEAN",
                "unresolved_review_threads": 0,
                "ci_state": "FAILURE",
            },
            base_dir=self.base,
        )
        self.assertFalse(blocked["advanced"])
        self.assertIn("CI failing", blocked["reason"])

    def test_high_risk_checkpoint_and_feed(self):
        from plate_core.checkpoint import decide_checkpoint

        r = start_feature_loop(
            feature_number=14,
            feature_title="API break",
            risk="high",
            labels=["Feature", "need:human-review"],
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(r["run"]["requires_human"])
        rid = r["run"]["id"]
        update_feature_loop(rid, stage="babysit", pr_number=1, base_dir=self.base)
        out = advance_feature_loop(rid, base_dir=self.base)
        self.assertEqual(out["to_stage"], "human_checkpoint")
        # #648 bridge: auto-open durable checkpoint + packet decide options
        cid = out.get("checkpoint_id") or out["run"].get("checkpoint_id")
        self.assertTrue(cid and str(cid).startswith("cp-"))
        pkt = out["packet"]
        self.assertEqual(pkt.get("checkpoint_id"), cid)
        self.assertTrue(any(o.get("id") == "approve" for o in pkt["ask_user_question"]["options"]))
        blocked = advance_feature_loop(rid, base_dir=self.base)
        self.assertFalse(blocked["advanced"])
        decide_checkpoint(
            cid,
            "approve",
            decided_by="test",
            base_dir=self.base / "checkpoints",
        )
        ok = advance_feature_loop(rid, base_dir=self.base)
        self.assertTrue(ok["advanced"])
        self.assertEqual(ok["to_stage"], "merge_eligible")
        feed = feature_loop_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        t = run_feature_loop_tick(rid, dry_run=True, base_dir=self.base)
        self.assertTrue(t["ok"])
        cancel_feature_loop(rid, base_dir=self.base)
        self.assertEqual(list_feature_loops(status="active", base_dir=self.base), [])

    def test_human_media(self):
        a = assess_human_required(risk="low", needs_media_approval=True, risk_tolerance="medium")
        # media alone with low risk and medium tolerance may not force required
        # but high risk does
        b = assess_human_required(risk="high", needs_media_approval=True)
        self.assertTrue(b["required"])


if __name__ == "__main__":
    unittest.main()
