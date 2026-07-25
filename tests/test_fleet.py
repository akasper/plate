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
        )
        self.assertEqual(acc["handoff"]["status"], "accepted")

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
