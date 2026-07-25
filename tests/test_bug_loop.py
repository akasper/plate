"""Tests for autonomous bug resolution loop (#638)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.bug_loop import (
    advance_bug_loop,
    assess_human_required,
    bug_loop_feed_items,
    cancel_bug_loop,
    estimate_bug_cost,
    list_bug_loops,
    next_stage,
    run_bug_loop_tick,
    start_bug_loop,
)


class TestStages(unittest.TestCase):
    def test_next_stage_order(self):
        self.assertEqual(next_stage("plan"), "open_pr_draft")
        self.assertEqual(next_stage("babysit", skip_checkpoint=True), "merge_eligible")
        self.assertEqual(next_stage("merge_eligible"), "done")

    def test_human_required(self):
        a = assess_human_required(risk="low", labels=["Bug"])
        self.assertFalse(a["required"])
        b = assess_human_required(risk="high", labels=[])
        self.assertTrue(b["required"])
        c = assess_human_required(risk="low", labels=["need:human-review"])
        self.assertTrue(c["required"])

    def test_estimate_grows(self):
        base = estimate_bug_cost(size="small", needs_repro=False)
        rich = estimate_bug_cost(size="small", needs_repro=True, e2e=True)
        self.assertGreater(rich["estimated_tokens"], base["estimated_tokens"])


class TestRunLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_start_advance_to_done_low_risk(self):
        r = start_bug_loop(
            bug_number=42,
            bug_title="Labels flake",
            risk="low",
            risk_tolerance="medium",
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(r["ok"])
        rid = r["run"]["id"]
        self.assertEqual(r["run"]["stage"], "plan")
        self.assertFalse(r["run"]["requires_human"])

        # advance through stages skipping checkpoint (low risk)
        stage = "plan"
        for _ in range(10):
            out = advance_bug_loop(rid, base_dir=self.base)
            self.assertTrue(out["ok"])
            if not out.get("advanced"):
                break
            stage = out["to_stage"]
            if stage == "done":
                break
        self.assertEqual(stage, "done")
        runs = list_bug_loops(status="done", base_dir=self.base)
        self.assertEqual(len(runs), 1)

    def test_high_risk_hits_checkpoint(self):
        r = start_bug_loop(
            bug_number=7,
            bug_title="Auth bug",
            risk="high",
            labels=["Bug", "need:human-review"],
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(r["run"]["requires_human"])
        rid = r["run"]["id"]
        # jump to babysit then advance
        from plate_core.bug_loop import update_bug_loop
        from plate_core.checkpoint import decide_checkpoint

        update_bug_loop(rid, stage="babysit", pr_number=100, base_dir=self.base)
        out = advance_bug_loop(rid, base_dir=self.base)
        self.assertEqual(out["to_stage"], "human_checkpoint")
        # #648 bridge: entering human_checkpoint auto-opens a durable checkpoint
        self.assertTrue(out.get("checkpoint_id") or out["run"].get("checkpoint_id"))
        cid = out.get("checkpoint_id") or out["run"]["checkpoint_id"]
        self.assertTrue(str(cid).startswith("cp-"))
        # Cannot leave without approval
        blocked = advance_bug_loop(rid, base_dir=self.base)
        self.assertFalse(blocked["advanced"])
        self.assertEqual(blocked["run"]["stage"], "human_checkpoint")
        # Approve then advance
        decide_checkpoint(
            cid,
            "approve",
            decided_by="test",
            base_dir=self.base / "checkpoints",
        )
        ok = advance_bug_loop(rid, base_dir=self.base)
        self.assertTrue(ok["advanced"])
        self.assertEqual(ok["to_stage"], "merge_eligible")

    def test_budget_blocks(self):
        r = start_bug_loop(
            bug_number=5,
            bug_title="huge",
            size="large",
            budget_remaining=100,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["blocked"])
        self.assertEqual(r["run"]["status"], "blocked")
        self.assertIsNotNone(r["run"]["cost_estimate_tokens"])

    def test_live_budget_hydrate_blocks(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from plate_core.autonomy import save_budget_spend

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            save_budget_spend(
                {"spent_today": 9800, "spent_this_cycle": 0, "spent_usd_today": 0.0},
                base_dir=bdir,
            )

            class _Cfg:
                autonomy = {
                    "enabled": True,
                    "risk_tolerance": "medium",
                    "token_budget": {"daily": 10000, "per_cycle": 8000, "action": "pause"},
                }

            with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
                r = start_bug_loop(
                    bug_number=6,
                    bug_title="live",
                    size="large",
                    use_live_budget=True,
                    budget_base_dir=bdir,
                    base_dir=self.base,
                    record_ledger=False,
                )
            self.assertTrue(r["blocked"])
            self.assertIn("budget_snapshot", r)

    def test_babysit_gate_blocks_advance(self):
        r = start_bug_loop(
            bug_number=1,
            bug_title="x",
            pr_number=9,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        self.assertEqual(r["run"]["stage"], "babysit")
        out = advance_bug_loop(
            rid,
            gates={"merge_state": "BLOCKED", "unresolved_review_threads": 0},
            base_dir=self.base,
        )
        self.assertTrue(out["ok"])
        self.assertFalse(out["advanced"])
        self.assertEqual(out["run"]["stage"], "babysit")

        out2 = advance_bug_loop(
            rid,
            gates={"merge_state": "CLEAN", "unresolved_review_threads": 0},
            base_dir=self.base,
        )
        self.assertTrue(out2["advanced"])

    def test_babysit_blocks_on_ci_and_changes_requested(self):
        """#638/#639: CI fail + CHANGES_REQUESTED must hold the loop on babysit."""
        r = start_bug_loop(
            bug_number=2,
            bug_title="ci",
            pr_number=11,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        ci_block = advance_bug_loop(
            rid,
            gates={
                "merge_state": "CLEAN",
                "unresolved_review_threads": 0,
                "ci_failing": True,
                "failing_checks": 2,
            },
            base_dir=self.base,
        )
        self.assertFalse(ci_block["advanced"])
        self.assertIn("CI failing", ci_block["reason"])

        review_block = advance_bug_loop(
            rid,
            gates={
                "merge_state": "CLEAN",
                "unresolved_review_threads": 0,
                "review_decision": "CHANGES_REQUESTED",
            },
            base_dir=self.base,
        )
        self.assertFalse(review_block["advanced"])
        self.assertIn("CHANGES_REQUESTED", review_block["reason"])

        pending = advance_bug_loop(
            rid,
            gates={
                "merge_state": "CLEAN",
                "unresolved_review_threads": 0,
                "ci_pending": True,
                "pending_checks": 1,
            },
            base_dir=self.base,
        )
        self.assertFalse(pending["advanced"])
        self.assertIn("CI pending", pending["reason"])

    def test_tick_dry_and_feed(self):
        r = start_bug_loop(
            bug_number=3,
            bug_title="feed me",
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        rid = r["run"]["id"]
        t = run_bug_loop_tick(rid, dry_run=True, base_dir=self.base)
        self.assertTrue(t["ok"])
        self.assertTrue(t["dry_run"])
        self.assertIn("packet", t)
        feed = bug_loop_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        cancel_bug_loop(rid, base_dir=self.base)
        self.assertEqual(list_bug_loops(status="active", base_dir=self.base), [])


if __name__ == "__main__":
    unittest.main()
