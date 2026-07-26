"""Tests for scheduled autonomous operations (#641)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plate_core.scheduled_ops import (
    estimate_op_cost,
    get_op,
    list_ops,
    list_op_runs,
    plan_op,
    run_procedure_dispatch,
    run_scheduled_op,
    scheduled_ops_status,
)


class TestCatalog(unittest.TestCase):
    def test_ops_present(self):
        ids = {o["id"] for o in list_ops()}
        for need in (
            "scheduled-refactor",
            "release-cut-prep",
            "deploy-production",
            "marketplace-package",
            "implement-epic-slice",
        ):
            self.assertIn(need, ids)
        self.assertIsNotNone(get_op("scheduled-refactor"))


class TestRunGates(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_dry_run_refactor_ok(self):
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "dry-run")
        self.assertTrue(out["packet"]["steps"])
        # #645: medium+ ops attach shadow preview (diff/worktree)
        self.assertTrue(out.get("shadow_id") or out["packet"].get("shadow_id"))
        # #641: dry-run previews fleet handoff without writing
        fd = out.get("fleet_dispatch") or {}
        self.assertTrue(fd.get("dry_run"))
        self.assertEqual(fd.get("to_agent"), "implementer")

    def test_live_refactor_dispatches_fleet_handoff(self):
        """#641: live scheduled-refactor opens a #644 implementer handoff."""
        import tempfile
        from pathlib import Path

        from plate_core.fleet import list_handoffs
        from plate_core.scheduled_ops import run_scheduled_op

        with tempfile.TemporaryDirectory() as tmp:
            ops_dir = Path(tmp) / "ops"
            fleet_dir = Path(tmp) / "fleet"
            out = run_scheduled_op(
                "scheduled-refactor",
                dry_run=False,
                risk_tolerance="medium",
                base_dir=ops_dir,
                fleet_base_dir=fleet_dir,
                record_ledger=False,
                budget_remaining=100_000,
                use_live_budget=False,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["status"], "executed")
            fd = out.get("fleet_dispatch") or {}
            self.assertTrue(fd.get("ok"), fd)
            self.assertTrue(fd.get("handoff_id"))
            self.assertEqual(fd.get("to_agent"), "implementer")
            rows = list_handoffs(status="active", base_dir=fleet_dir)
            self.assertTrue(any(h.get("handoff_id") == fd.get("handoff_id") for h in rows))
            self.assertEqual(
                (out.get("run") or {}).get("metadata", {}).get("fleet_handoff_id"),
                fd.get("handoff_id"),
            )

    def test_deploy_op_skips_fleet_auto_dispatch(self):
        """Critical deploy never auto-opens fleet handoffs without human path."""
        from plate_core.scheduled_ops import dispatch_fleet_for_scheduled_op

        out = dispatch_fleet_for_scheduled_op("deploy-production")
        self.assertTrue(out.get("skipped"))

    def test_critical_blocked_without_approve(self):
        out = run_scheduled_op(
            "deploy-production",
            dry_run=True,
            risk_tolerance="high",
            approved=False,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
        )
        self.assertFalse(out["ok"])
        self.assertTrue(out["blocked"])
        # Still get a shadow preview when blocked
        self.assertIn("shadow_report", out)
        self.assertTrue(out["shadow_report"].get("worktree_plan"))

    def test_critical_ok_with_approve(self):
        out = run_scheduled_op(
            "deploy-production",
            dry_run=True,
            risk_tolerance="high",
            approved=True,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("shadow_id"))

    def test_plan_and_status(self):
        p = plan_op("release-cut-prep")
        self.assertTrue(p["ok"])
        st = scheduled_ops_status(risk_tolerance="low", base_dir=self.base)
        self.assertGreater(st["n_ops"], 0)
        self.assertTrue(st["gated"])

    def test_dispatch_unknown(self):
        self.assertIsNone(run_procedure_dispatch("not-an-op", base_dir=self.base))
        d = run_procedure_dispatch(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            use_live_budget=False,
        )
        self.assertTrue(d["ok"])
        self.assertTrue(list_op_runs(base_dir=self.base))

    def test_estimate_op_cost(self):
        dry = estimate_op_cost("scheduled-refactor", dry_run=True)
        apply = estimate_op_cost("scheduled-refactor", dry_run=False)
        self.assertTrue(dry["ok"])
        self.assertGreater(apply["estimated_tokens"], dry["estimated_tokens"])
        self.assertGreater(dry["estimated_tokens"], 0)
        bad = estimate_op_cost("no-such-op")
        self.assertFalse(bad["ok"])

    def test_budget_blocks_when_est_exceeds_remaining(self):
        est = estimate_op_cost("scheduled-refactor", dry_run=True)["estimated_tokens"]
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=False,
            budget_remaining=max(0, est - 1),
            use_live_budget=False,
        )
        self.assertFalse(out["ok"])
        self.assertTrue(out["blocked"])
        self.assertIn("budget", out.get("error") or "")
        self.assertEqual(out.get("cost_estimate_tokens"), est)
        self.assertEqual(out.get("budget_remaining"), max(0, est - 1))

    def test_budget_allows_when_remaining_sufficient_no_charge(self):
        est = estimate_op_cost("scheduled-refactor", dry_run=True)["estimated_tokens"]
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=False,
            budget_remaining=est + 1000,
            use_live_budget=False,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out.get("budget_remaining"), est + 1000)
        self.assertIn("cost_estimate_tokens", out)
        self.assertNotIn("budget_charge", out)

    def test_plan_includes_cost_estimate(self):
        p = plan_op("scheduled-refactor")
        self.assertTrue(p["ok"])
        self.assertIn("cost_estimate", p)
        self.assertGreater(p["cost_estimate"]["estimated_tokens"], 0)

    def test_status_includes_budget_fields(self):
        st = scheduled_ops_status(
            risk_tolerance="medium",
            base_dir=self.base,
            include_budget=True,
        )
        self.assertIn("budget_remaining_tokens", st)
        # Runnable items carry estimates
        for row in st.get("runnable_at_tolerance") or []:
            self.assertIn("estimated_tokens_dry_run", row)


if __name__ == "__main__":
    unittest.main()
