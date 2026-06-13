"""Basic unit tests for AutonomyEngine (Epic #470 / #482).

Tests cover config loading, risk filtering, budget enforcement (daily reset, throttle/pause),
procedure loading from .agentic/procedures/, tick_schedules, and basic cycle/report.
E2E simulation for loop under budget would use mocks for health/epics/costs and assert
no overspend + terse output (see quiet ops in agent_guidance). Added as stub for #482.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from plate_core.autonomy import AutonomyEngine, Decision, ProcedureDef


class TestAutonomyEngine(unittest.TestCase):

    def test_load_procedures_builtin(self):
        engine = AutonomyEngine(repo=None)
        ids = [p.id for p in engine.procedures]
        self.assertIn("nightly-drift-detection", ids)
        self.assertIn("feedback-integration", ids)

    def test_load_procedures_from_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            proc_dir = tmp_path / ".agentic" / "procedures"
            proc_dir.mkdir(parents=True)
            (proc_dir / "custom-proc.json").write_text(json.dumps({
                "id": "custom-proc",
                "cadence": "nightly",
                "risk_level": "low",
                "description": "custom test procedure",
                "enabled": True,
            }))
            orig_dir = os.getcwd()
            try:
                os.chdir(tmp_path)
                engine = AutonomyEngine(repo=None)
                ids = [p.id for p in engine.procedures]
                self.assertIn("custom-proc", ids)
                self.assertIn("nightly-drift-detection", ids)
            finally:
                os.chdir(orig_dir)

    def test_risk_filter_and_due(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.procedures = [
            ProcedureDef(id="low-proc", cadence="nightly", risk_level="low", enabled=True),
            ProcedureDef(id="high-proc", cadence="nightly", risk_level="high", enabled=True),
        ]
        due = engine.tick_schedules()
        ids = [d["id"] for d in due]
        self.assertIn("low-proc", ids)
        self.assertNotIn("high-proc", ids)

    def test_enforce_budget_throttle(self):
        engine = AutonomyEngine(repo=None)
        engine.autonomy_config = {"token_budget": {"daily": 1000, "per_cycle": 500, "action": "throttle"}}
        engine.enabled = True  # test exercises enforcement path (default now conservative False per Epic #470; test must opt-in)
        engine.risk_tolerance = "high"
        engine.enabled = True
        engine._spent_this_cycle = 0
        # First spend within limits
        self.assertEqual(engine.enforce_budget(400, "test"), Decision.PROCEED)
        self.assertEqual(engine._spent_this_cycle, 400)
        # Over per_cycle -> throttle (partial spend, still proceeds)
        self.assertEqual(engine.enforce_budget(200, "test"), Decision.THROTTLE)
        self.assertGreaterEqual(engine._spent_this_cycle, 400)

    def test_enforce_budget_pause(self):
        engine = AutonomyEngine(repo=None)
        engine.autonomy_config = {"token_budget": {"daily": 1000, "per_cycle": 100, "action": "pause"}}
        engine.risk_tolerance = "high"
        engine.enabled = True
        engine._spent_this_cycle = 0
        # Under limit: proceeds
        self.assertEqual(engine.enforce_budget(50, "test"), Decision.PROCEED)
        # Over per_cycle -> pause returns Decision.PAUSE
        self.assertEqual(engine.enforce_budget(200, "test"), Decision.PAUSE)

    def test_get_status_and_autopilot(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "high"
        engine.autonomy_config = {"token_budget": {"daily": 10000}}
        status = engine.get_status()
        self.assertEqual(status.risk_tolerance, "high")
        self.assertGreaterEqual(status.autopilot_score, 0)
        self.assertLessEqual(status.autopilot_score, 100)
        self.assertIn("due_procedures", status.to_dict())

    def test_run_cycle_dry_run(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        report = engine.run_cycle(dry_run=True, max_steps=2)
        self.assertIn(report.status, ("completed", "paused"))
        self.assertIsInstance(report.actions_taken, list)
        self.assertIn(report.budget_decision, ("proceed", "throttle", "pause", "warn"))

    def test_run_cycle_pause_on_budget_exceeded(self):
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.autonomy_config = {"token_budget": {"daily": 1, "per_cycle": 1, "action": "pause"}}
        engine.enabled = True
        engine._spent_this_cycle = 100
        report = engine.run_cycle(dry_run=True, max_steps=5)
        self.assertEqual(report.status, "paused")
        self.assertTrue(report.paused)
        self.assertEqual(report.budget_decision, "pause")

    def test_estimate_cost_heuristics(self):
        """#471 wired: base + scope mult + over-est (1.5-2x+20%) + cap; references costs/COSTS for hist (sparse ok)."""
        engine = AutonomyEngine(repo=None)
        engine.autonomy_config = {"token_budget": {"per_cycle": 8000}}
        est1 = engine.estimate_cost("info_audit")
        self.assertGreater(est1, 2000)  # over+buffer applied (capped by per_cycle=8k)
        self.assertLessEqual(est1, 7200)  # capped <90% of 8k per #471
        est2 = engine.estimate_cost("health", {"num_items": 10})
        self.assertGreater(est2, 400)  # scope mult
        est3 = engine.estimate_cost("plan_epic")
        self.assertGreaterEqual(est3, 5000)

    def test_decide_next_budget_wired(self):
        """decide_next calls est + enforce per #474; filters PAUSE, annotates decision."""
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "medium"
        engine.enabled = True
        engine.autonomy_config = {"token_budget": {"per_cycle": 100, "daily": 1000, "action": "throttle"}}
        snap = engine.introspect()
        acts = engine.decide_next(snap)
        self.assertIsInstance(acts, list)
        if acts:
            self.assertIn("est", acts[0])
            self.assertIn("decision", acts[0])

    def test_get_status_burn_rate_and_autopilot(self):
        """#479 complete: burn_rate in status + enhanced autopilot composite."""
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "high"
        engine.autonomy_config = {"token_budget": {"daily": 10000}}
        engine._spent_today = 2500
        status = engine.get_status()
        self.assertGreaterEqual(status.autopilot_score, 0)
        self.assertLessEqual(status.autopilot_score, 100)
        self.assertIn("burn_rate", status.to_dict())
        self.assertGreaterEqual(status.burn_rate, 0.0)
        d = status.to_dict()
        self.assertIn("burn_rate", d)


if __name__ == "__main__":
    unittest.main()




