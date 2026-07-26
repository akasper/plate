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
            "review-discussions",
            "monitor-market",
        ):
            self.assertIn(need, ids)
        self.assertIsNotNone(get_op("scheduled-refactor"))
        self.assertEqual(get_op("review-discussions")["risk_level"], "low")


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

    def test_review_discussions_dry_run_and_live_fleet(self):
        """#642: review-discussions dry-run attaches monitor; live opens market-monitor handoff."""
        import tempfile
        from pathlib import Path

        from plate_core.fleet import list_handoffs
        from plate_core.scheduled_ops import run_scheduled_op

        with tempfile.TemporaryDirectory() as tmp:
            ops_dir = Path(tmp) / "ops"
            fleet_dir = Path(tmp) / "fleet"
            dry = run_scheduled_op(
                "review-discussions",
                dry_run=True,
                risk_tolerance="medium",
                base_dir=ops_dir,
                record_ledger=False,
                budget_remaining=100_000,
                use_live_budget=False,
            )
            self.assertTrue(dry["ok"], dry)
            self.assertIn("monitor", dry)
            self.assertTrue((dry.get("fleet_dispatch") or {}).get("dry_run"))
            self.assertEqual((dry.get("fleet_dispatch") or {}).get("to_agent"), "market-monitor")

            live = run_scheduled_op(
                "review-discussions",
                dry_run=False,
                risk_tolerance="low",
                base_dir=ops_dir,
                fleet_base_dir=fleet_dir,
                record_ledger=False,
                budget_remaining=100_000,
                use_live_budget=False,
            )
            self.assertTrue(live["ok"], live)
            fd = live.get("fleet_dispatch") or {}
            self.assertTrue(fd.get("ok"), fd)
            self.assertEqual(fd.get("to_agent"), "market-monitor")
            rows = list_handoffs(status="active", base_dir=fleet_dir)
            self.assertTrue(any(h.get("handoff_id") == fd.get("handoff_id") for h in rows))

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

    def test_live_critical_requires_shadow_ack(self):
        """#879/#645: live high-impact ops need shadow_ack, not approve alone."""
        # approved without shadow_ack → blocked
        blocked = run_scheduled_op(
            "deploy-production",
            dry_run=False,
            risk_tolerance="high",
            approved=True,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
            dispatch_fleet=False,
        )
        self.assertFalse(blocked["ok"], blocked)
        self.assertTrue(blocked["blocked"])
        self.assertIn("shadow", (blocked.get("error") or "").lower())
        self.assertTrue(blocked.get("shadow_id"))

        # dry-run first for shadow_id, then live with ack + approve
        preview = run_scheduled_op(
            "deploy-production",
            dry_run=True,
            risk_tolerance="high",
            approved=False,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
        )
        sid = preview.get("shadow_id")
        self.assertTrue(sid)
        ok = run_scheduled_op(
            "deploy-production",
            dry_run=False,
            risk_tolerance="high",
            approved=True,
            shadow_ack=sid,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
            dispatch_fleet=False,
        )
        self.assertTrue(ok["ok"], ok)
        self.assertFalse(ok.get("blocked"))

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

    def test_budget_blocks_on_durable_would_pause_risk_off(self):
        """#871/#634: hard-block when remaining > 0 but next cycle would pause."""
        from unittest.mock import patch

        from plate_core.autonomy import save_budget_spend

        bdir = self.base / "budget"
        today = (
            __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .date()
            .isoformat()
        )
        save_budget_spend(
            {
                "date": today,
                "spent_today": 9000,
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
                    "daily": 10000,
                    "per_cycle": 2000,
                    "action": "pause",
                },
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            # review-discussions dry_run est is small (750) < remaining 1000,
            # so est-exceeds-remaining would NOT fire — would_pause must hard-block.
            out = run_scheduled_op(
                "review-discussions",
                dry_run=True,
                risk_tolerance="off",
                base_dir=self.base,
                record_ledger=False,
                use_live_budget=True,
            )

        self.assertFalse(out["ok"], out)
        self.assertTrue(out["blocked"])
        self.assertIn("budget", out.get("error") or "")
        self.assertTrue(out.get("would_pause_next_cycle"))
        self.assertEqual(out.get("budget_remaining"), 1000)
        self.assertEqual(out.get("budget_pressure"), "critical")

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

    def test_dry_run_never_charges_live_budget(self):
        """dry_run previews must not deplete durable spend even with use_live_budget."""
        from plate_core.autonomy import load_budget_spend, save_budget_spend
        from plate_core.ledger import list_decisions

        bdir = self.base / "budget"
        bdir.mkdir(parents=True, exist_ok=True)
        save_budget_spend(
            {
                "date": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .date()
                .isoformat(),
                "spent_today": 100,
                "spent_this_cycle": 0,
                "spent_usd_today": 0.0,
            },
            base_dir=bdir,
        )
        root_before = int((load_budget_spend() or {}).get("spent_today") or 0)
        root_ledger = len(list_decisions(limit=500))
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=True,
            risk_tolerance="medium",
            base_dir=self.base,
            record_ledger=True,
            use_live_budget=True,
        )
        self.assertTrue(out["ok"])
        self.assertNotIn("budget_charge", out)
        self.assertTrue(
            any("skipped budget charge" in n for n in (out.get("notes") or []))
        )
        local = load_budget_spend(base_dir=bdir)
        self.assertEqual(int(local.get("spent_today") or 0), 100)
        self.assertEqual(
            int((load_budget_spend() or {}).get("spent_today") or 0), root_before
        )
        # Ledger isolated under base_dir/ledger
        local_led = list_decisions(limit=20, base_dir=self.base / "ledger")
        self.assertTrue(any(x.get("id") == out.get("ledger_id") for x in local_led))
        self.assertEqual(len(list_decisions(limit=500)), root_ledger)

    def test_live_apply_charges_isolated_budget(self):
        """Non-dry_run charge stays under base_dir/budget, not repo root."""
        from plate_core.autonomy import load_budget_spend

        root_before = int((load_budget_spend() or {}).get("spent_today") or 0)
        est = estimate_op_cost("scheduled-refactor", dry_run=False)["estimated_tokens"]
        out = run_scheduled_op(
            "scheduled-refactor",
            dry_run=False,
            risk_tolerance="medium",
            approved=True,
            base_dir=self.base,
            record_ledger=False,
            budget_remaining=est + 5000,
            use_live_budget=True,
            dispatch_fleet=False,
        )
        self.assertTrue(out["ok"], out)
        self.assertIn("budget_charge", out)
        self.assertTrue((out.get("budget_charge") or {}).get("ok"))
        local = load_budget_spend(base_dir=self.base / "budget")
        self.assertEqual(int(local.get("spent_today") or 0), est)
        self.assertEqual(
            int((load_budget_spend() or {}).get("spent_today") or 0), root_before
        )

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

    def test_status_hydrates_budget_under_base_dir(self):
        """base_dir status must read base_dir/budget and expose would_pause_next_cycle."""
        from unittest.mock import patch

        from plate_core.autonomy import save_budget_spend

        bdir = self.base / "budget"
        today = (
            __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .date()
            .isoformat()
        )
        save_budget_spend(
            {
                "date": today,
                "spent_today": 0,
                "spent_this_cycle": 0,
                "spent_usd_today": 0.0,
            },
            base_dir=bdir,
        )

        class _Cfg:
            autonomy = {
                "enabled": True,
                "risk_tolerance": "medium",
                "token_budget": {
                    "daily": 10000,
                    "per_cycle": 2000,
                    "action": "pause",
                },
            }

        with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
            st = scheduled_ops_status(
                risk_tolerance="medium",
                base_dir=self.base,
                include_budget=True,
            )
        self.assertEqual(st.get("budget_remaining_tokens"), 10000)
        self.assertEqual(st.get("budget_pressure"), "ok")
        self.assertIn("would_pause_next_cycle", st)
        self.assertFalse(st.get("would_pause_next_cycle"))


class TestScheduledOpsSurfaceShadowAck881(unittest.TestCase):
    """#881: CLI/MCP must expose shadow_ack for live high-impact runs."""

    def test_cli_parser_has_shadow_ack(self):
        from plate_core.cli import build_parser

        p = build_parser()
        # parse scheduled-ops --run with --shadow-ack
        ns = p.parse_args(
            [
                "scheduled-ops",
                "--run",
                "deploy-production",
                "--apply",
                "--approved",
                "--shadow-ack",
                "shad-test-id",
            ]
        )
        self.assertEqual(ns.run, "deploy-production")
        self.assertTrue(ns.apply)
        self.assertTrue(ns.approved)
        self.assertEqual(ns.shadow_ack, "shad-test-id")

    def test_mcp_tool_schema_includes_shadow_ack(self):
        import json
        from pathlib import Path

        # Schema is embedded in mcp_server module source; assert property present.
        src = Path("src/plate_core/mcp_server.py").read_text(encoding="utf-8")
        self.assertIn("plate_scheduled_op_run", src)
        self.assertIn('"shadow_ack"', src)
        # Handler must pass the kwarg through
        self.assertIn("shadow_ack=args.get(\"shadow_ack\")", src)


if __name__ == "__main__":
    unittest.main()
