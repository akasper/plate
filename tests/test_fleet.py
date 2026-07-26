"""Tests for multi-agent fleet handoffs (#644)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.fleet import (
    allocate_fleet_budget,
    complete_handoff,
    create_handoff,
    estimate_handoff_cost,
    fleet_status,
    handoff_feed_items,
    handoff_from_pm_assignment,
    list_fleet_roles,
    list_handoffs,
    plan_fleet_from_intent,
    update_handoff,
)


class TestFleetRoles(unittest.TestCase):
    def test_roles_cover_story_agents(self):
        ids = {r["id"] for r in list_fleet_roles()}
        for need in ("planner", "implementer", "reviewer", "researcher", "deployer", "market-monitor"):
            self.assertIn(need, ids)


class TestHandoffs(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_create_list_complete(self):
        with patch("plate_core.fleet.record_decision", create=True):
            # avoid ledger side effects if import path differs
            pass
        r = create_handoff(
            from_agent="orchestrator",
            to_agent="implementer",
            task="Ship feature X",
            budget_tokens=4000,
            base_dir=self.base,
            record_ledger=False,
            use_live_budget=False,
        )
        self.assertTrue(r["ok"])
        hid = r["handoff"]["handoff_id"]
        open_h = list_handoffs(status="open", base_dir=self.base)
        self.assertEqual(len(open_h), 1)
        u = update_handoff(hid, status="accepted", base_dir=self.base, record_ledger=False)
        self.assertEqual(u["handoff"]["status"], "accepted")
        c = complete_handoff(hid, notes="done", artifacts=["PR #1"], base_dir=self.base)
        self.assertTrue(c["ok"])
        self.assertEqual(c["handoff"]["status"], "done")
        self.assertEqual(list_handoffs(status="active", base_dir=self.base), [])

    def test_requires_fields(self):
        self.assertFalse(create_handoff(from_agent="a", to_agent="", task="t", base_dir=self.base, record_ledger=False)["ok"])
        self.assertFalse(create_handoff(from_agent="a", to_agent="b", task="", base_dir=self.base, record_ledger=False)["ok"])


class TestBudgetAndPlan(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_allocate_sums(self):
        out = allocate_fleet_budget(10000, active_roles=["planner", "implementer", "reviewer"])
        self.assertTrue(out["ok"])
        total = sum(a["tokens"] for a in out["allocations"])
        self.assertEqual(total, 10000)

    def test_plan_dry_and_create(self):
        dry = plan_fleet_from_intent(
            "Plan the next release and start implementing the top features",
            budget_tokens=20000,
            use_live_budget=False,
            create=False,
            base_dir=self.base,
        )
        self.assertTrue(dry["dry_run"])
        self.assertTrue(dry["ok"])
        self.assertEqual(dry.get("budget_remaining_tokens"), 20000)
        self.assertGreaterEqual(len(dry["plan"]), 2)
        agents = {s["to_agent"] for s in dry["plan"]}
        self.assertIn("planner", agents)
        self.assertIn("implementer", agents)

        created = plan_fleet_from_intent(
            "Plan and implement features",
            budget_tokens=10000,
            use_live_budget=False,
            create=True,
            base_dir=self.base,
        )
        self.assertFalse(created["dry_run"])
        self.assertGreater(created["n_created"], 0)
        st = fleet_status(base_dir=self.base, use_live_budget=False)
        self.assertGreater(st["n_active"], 0)
        feed = handoff_feed_items(base_dir=self.base)
        self.assertTrue(feed)
        self.assertIn("ask_user_question", feed[0])

    def test_plan_blocks_on_zero_budget(self):
        out = plan_fleet_from_intent(
            "Implement features",
            budget_tokens=0,
            use_live_budget=False,
            create=True,
            base_dir=self.base,
        )
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("blocked"))
        self.assertEqual(out.get("n_created"), 0)
        self.assertIn("budget", out.get("error") or "")

    def test_plan_and_create_block_on_durable_would_pause(self):
        """#869/#634: fleet blocks when remaining > 0 but next cycle would pause."""
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
            plan = plan_fleet_from_intent(
                "Implement features",
                use_live_budget=True,
                create=True,
                base_dir=self.base,
            )
            ho = create_handoff(
                from_agent="orchestrator",
                to_agent="implementer",
                task="blocked by rails",
                budget_tokens=500,
                use_live_budget=True,
                base_dir=self.base,
                record_ledger=False,
            )

        self.assertFalse(plan.get("ok"), plan)
        self.assertTrue(plan.get("blocked"))
        self.assertEqual(plan.get("reason"), "budget")
        self.assertEqual(plan.get("n_created"), 0)
        self.assertTrue(plan.get("would_pause_next_cycle"))
        self.assertEqual(plan.get("budget_remaining_tokens"), 1000)

        self.assertFalse(ho.get("ok"), ho)
        self.assertTrue(ho.get("blocked"))
        self.assertEqual(ho.get("reason"), "budget")
        self.assertTrue(ho.get("would_pause_next_cycle"))

    def test_plan_and_status_hydrate_budget_under_base_dir(self):
        """base_dir alone hydrates remaining from base_dir/budget (#634/#644)."""
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
                "spent_today": 8000,
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
            plan = plan_fleet_from_intent(
                "Implement features",
                use_live_budget=True,
                create=False,
                base_dir=self.base,
            )
            st = fleet_status(base_dir=self.base, use_live_budget=True)
        self.assertTrue(plan.get("ok"), plan)
        self.assertEqual(plan.get("budget_remaining_tokens"), 2000)
        self.assertTrue(
            any("budget hydrated" in n for n in (plan.get("notes") or [])),
            plan.get("notes"),
        )
        self.assertEqual(st.get("budget_remaining_tokens"), 2000)

    def test_budget_gate_and_blocked_high_risk(self):
        blocked = create_handoff(
            from_agent="orchestrator",
            to_agent="implementer",
            task="big work",
            budget_tokens=5000,
            budget_remaining=100,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked.get("blocked"))
        self.assertEqual(blocked.get("cost_estimate_tokens"), 5000)

        hi = create_handoff(
            from_agent="orchestrator",
            to_agent="deployer",
            task="Deploy prod",
            risk="high",
            requires_human=True,
            open_checkpoint=True,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(hi["ok"])
        self.assertEqual(hi["handoff"]["status"], "blocked")
        self.assertIsNotNone(hi.get("cost_estimate_tokens"))
        # Checkpoint isolation: must land under fleet base_dir, not repo root
        cp_id = hi.get("checkpoint_id")
        self.assertIsNotNone(cp_id)
        isolated = self.base / "checkpoints"
        self.assertTrue(
            isolated.is_dir(),
            "fleet base_dir must own checkpoints to avoid polluting .agentic/checkpoints",
        )
        self.assertTrue(any(isolated.glob(f"{cp_id}*.json")))
        # active includes blocked
        active = list_handoffs(status="active", base_dir=self.base)
        self.assertTrue(any(h.get("status") == "blocked" for h in active))
        feed = handoff_feed_items(base_dir=self.base)
        self.assertTrue(any(f.get("status") == "blocked" for f in feed))
        acc = update_handoff(
            hi["handoff"]["handoff_id"],
            status="accepted",
            base_dir=self.base,
            record_ledger=False,
            dispatch_work=True,
        )
        self.assertEqual(acc["handoff"]["status"], "accepted")
        # deployer → packet_only (no silent deploy)
        self.assertEqual((acc.get("dispatch") or {}).get("dispatch_kind"), "packet_only")

    def test_create_handoff_isolates_budget_and_ledger(self):
        """use_live_budget + base_dir must not touch repo-root spend.json / ledger."""
        from plate_core.autonomy import get_budget_snapshot, load_budget_spend
        from plate_core.ledger import list_decisions

        before_root = load_budget_spend() or {}
        before_spent = int(before_root.get("spent_today") or 0)
        before_ledger_n = len(list_decisions(limit=500))

        r = create_handoff(
            from_agent="orchestrator",
            to_agent="implementer",
            task="Isolate budget charge",
            budget_tokens=1500,
            use_live_budget=True,
            base_dir=self.base,
            record_ledger=True,
        )
        self.assertTrue(r["ok"])
        self.assertIsNotNone(r.get("ledger_id"))
        # Charge only under base_dir/budget
        local_spend = load_budget_spend(base_dir=self.base / "budget")
        self.assertEqual(int(local_spend.get("spent_today") or 0), 1500)
        # Repo-root spend unchanged
        after_root = load_budget_spend() or {}
        self.assertEqual(int(after_root.get("spent_today") or 0), before_spent)
        # Ledger under base_dir/ledger only
        local_led = list_decisions(limit=50, base_dir=self.base / "ledger")
        self.assertTrue(any(x.get("id") == r.get("ledger_id") for x in local_led))
        after_ledger_n = len(list_decisions(limit=500))
        self.assertEqual(after_ledger_n, before_ledger_n)
        # Isolated hydrate also sees local remaining
        snap = get_budget_snapshot(base_dir=self.base / "budget")
        self.assertEqual(snap.get("spent_today"), 1500)

    def test_accept_implementer_dispatches_feature_loop(self):
        """#644: accepting implementer handoff opens a durable feature loop."""
        import tempfile
        from pathlib import Path

        from plate_core.fleet import create_handoff, update_handoff
        from plate_core.feature_loop import list_feature_loops

        with tempfile.TemporaryDirectory() as tmp:
            fleet_dir = Path(tmp) / "fleet"
            feat_dir = Path(tmp) / "feats"
            created = create_handoff(
                from_agent="orchestrator",
                to_agent="implementer",
                task="Implement feed ranking",
                related_issue=88,
                risk="medium",
                budget_tokens=4000,
                budget_remaining=50_000,
                use_live_budget=False,
                base_dir=fleet_dir,
                record_ledger=False,
            )
            self.assertTrue(created["ok"], created)
            hid = created["handoff"]["handoff_id"]
            acc = update_handoff(
                hid,
                status="accepted",
                base_dir=fleet_dir,
                record_ledger=False,
                feature_loop_base_dir=feat_dir,
            )
            self.assertEqual(acc["handoff"]["status"], "accepted")
            disp = acc.get("dispatch") or {}
            self.assertTrue(disp.get("ok"), disp)
            self.assertEqual(disp.get("dispatch_kind"), "feature_loop")
            self.assertTrue(disp.get("run_id"))
            self.assertEqual(
                (acc["handoff"].get("context") or {}).get("loop_run_id"),
                disp.get("run_id"),
            )
            loops = list_feature_loops(status="active", base_dir=feat_dir)
            self.assertTrue(any(r.get("id") == disp.get("run_id") for r in loops))

    def test_accept_researcher_dispatches_artifact(self):
        """#644: accepting researcher handoff opens a #632 pending artifact."""
        import tempfile
        from pathlib import Path

        from plate_core.design_research_approval import get_proposal
        from plate_core.fleet import create_handoff, update_handoff

        with tempfile.TemporaryDirectory() as tmp:
            fleet_dir = Path(tmp) / "fleet"
            art_dir = Path(tmp) / "artifacts"
            created = create_handoff(
                from_agent="orchestrator",
                to_agent="researcher",
                task="Research competitor onboarding friction",
                related_issue=42,
                risk="low",
                budget_tokens=2000,
                budget_remaining=50_000,
                use_live_budget=False,
                base_dir=fleet_dir,
                record_ledger=False,
            )
            hid = created["handoff"]["handoff_id"]
            acc = update_handoff(
                hid,
                status="accepted",
                base_dir=fleet_dir,
                record_ledger=False,
                artifact_base_dir=art_dir,
            )
            disp = acc.get("dispatch") or {}
            self.assertTrue(disp.get("ok"), disp)
            self.assertEqual(disp.get("dispatch_kind"), "artifact")
            prop = get_proposal(disp["run_id"], base_dir=art_dir)
            self.assertIsNotNone(prop)
            self.assertEqual(prop["kind"], "research")
            self.assertEqual(prop["related_issue"], 42)

    def test_pm_assignment_bridge(self):
        out = handoff_from_pm_assignment(
            {
                "assignment_id": "asg-1",
                "agent_id": "dev-cautious",
                "work_title": "Implement auth",
                "work_type": "implement",
                "estimated_tokens": 3000,
                "impact": "medium",
            },
            budget_remaining=10000,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["handoff"]["to_agent"], "implementer")
        self.assertEqual(out["pm_assignment_id"], "asg-1")

    def test_pm_design_persona_maps_to_researcher(self):
        out = handoff_from_pm_assignment(
            {
                "assignment_id": "asg-d1",
                "agent_id": "design-minimal",
                "work_title": "Wireframes for feed",
                "work_type": "design",
                "estimated_tokens": 2000,
                "impact": "low",
            },
            budget_remaining=10000,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["handoff"]["to_agent"], "researcher")

    def test_estimate_handoff_cost(self):
        est = estimate_handoff_cost(to_agent="implementer", risk="medium")
        self.assertTrue(est["ok"])
        self.assertGreater(est["estimated_tokens"], 0)
        explicit = estimate_handoff_cost(budget_tokens=1234)
        self.assertEqual(explicit["estimated_tokens"], 1234)

    def test_estimate_fills_budget_tokens_and_status_remaining(self):
        out = create_handoff(
            from_agent="orchestrator",
            to_agent="implementer",
            task="estimate fill",
            budget_remaining=50000,
            use_live_budget=False,
            base_dir=self.base,
            record_ledger=False,
        )
        self.assertTrue(out["ok"])
        self.assertIsNotNone(out["handoff"].get("budget_tokens"))
        self.assertGreater(out["handoff"]["budget_tokens"], 0)
        st = fleet_status(
            budget_remaining=8000,
            use_live_budget=False,
            base_dir=self.base,
        )
        self.assertEqual(st.get("budget_remaining_tokens"), 8000)
        self.assertIsNotNone(st.get("budget"))


if __name__ == "__main__":
    unittest.main()
