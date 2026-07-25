"""Tests for provenance + decision ledger (#647)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.ledger import (
    get_decision,
    ledger_summary,
    list_decisions,
    query_decisions,
    record_decision,
    record_from_autonomy_action,
    render_decision_marker,
)


class TestLedger647(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "ledger"
        self.base.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_and_get(self):
        out = record_decision(
            "release_cut",
            "pause",
            "budget near cap",
            sources=["autonomy_status", "costs"],
            cost_estimate_tokens=9000,
            risk_tolerance="medium",
            impact="critical",
            related_issue=647,
            base_dir=self.base,
        )
        self.assertTrue(out["id"].startswith("dec-"))
        self.assertIn("PLATE-DECISION:BEGIN", out["marker"])
        got = get_decision(out["id"], base_dir=self.base)
        self.assertIsNotNone(got)
        self.assertEqual(got["action_kind"], "release_cut")
        self.assertEqual(got["decision"], "pause")
        self.assertEqual(got["related_issue"], 647)
        self.assertEqual(got["sources"], ["autonomy_status", "costs"])

    def test_list_and_filter(self):
        record_decision("what_next", "proceed", "ok", base_dir=self.base)
        record_decision("run_procedure", "throttle", "near cap", base_dir=self.base, related_issue=1)
        all_rows = list_decisions(base_dir=self.base)
        self.assertEqual(len(all_rows), 2)
        throttled = list_decisions(decision="throttle", base_dir=self.base)
        self.assertEqual(len(throttled), 1)
        by_issue = list_decisions(related_issue=1, base_dir=self.base)
        self.assertEqual(len(by_issue), 1)

    def test_query_substring(self):
        record_decision(
            "deploy",
            "shadow_required",
            "critical impact needs approval",
            sources=["shadow:shadow-1"],
            shadow_id="shadow-1",
            base_dir=self.base,
        )
        hits = query_decisions("shadow-1", base_dir=self.base)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["action_kind"], "deploy")
        misses = query_decisions("not-present-xyz", base_dir=self.base)
        self.assertEqual(misses, [])

    def test_record_from_autonomy_action(self):
        out = record_from_autonomy_action(
            {
                "type": "what_next",
                "decision": "throttle",
                "est": 1500,
                "throttled": True,
                "annotation": "WARN: budget",
            },
            risk_tolerance="low",
            session="sess-1",
            base_dir=self.base,
        )
        self.assertEqual(out["action_kind"], "what_next")
        self.assertEqual(out["decision"], "throttle")
        self.assertEqual(out["cost_estimate_tokens"], 1500)
        self.assertIn("throttled", out["reason"])

    def test_marker_render(self):
        out = record_decision("babysit", "proceed", "threads resolved", base_dir=self.base)
        m = out["marker"]
        self.assertIn("PLATE-DECISION", m)
        self.assertIn("babysit", m)

    def test_summary(self):
        record_decision("a", "proceed", "r", base_dir=self.base)
        record_decision("b", "pause", "r", base_dir=self.base)
        s = ledger_summary(base_dir=self.base)
        self.assertEqual(s["count"], 2)
        self.assertIn("proceed", s["by_decision"])
        self.assertIn("pause", s["by_decision"])


class TestAutonomyLedgerWire(unittest.TestCase):
    def test_run_cycle_writes_ledger_entries(self):
        from plate_core.autonomy import AutonomyEngine

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "ledger"
            base.mkdir()
            with patch("plate_core.ledger.LEDGER_DIR", base), patch(
                "plate_core.ledger._ensure_dir",
                side_effect=lambda b=None: base if b is None else Path(b),
            ), patch(
                "plate_core.autonomy.get_cost_report",
                side_effect=Exception("no network"),
            ), patch(
                "plate_core.autonomy.get_health",
                side_effect=Exception("no network"),
            ), patch(
                "plate_core.autonomy.get_epic_status",
                side_effect=Exception("no network"),
            ), patch(
                "plate_core.autonomy.get_plate_config_report",
                return_value=type("R", (), {"to_dict": lambda self: {}})(),
            ), patch(
                "plate_core.autonomy.load_plate_config",
                return_value=type(
                    "C",
                    (),
                    {
                        "to_dict": lambda self: {
                            "autonomy": {
                                "enabled": True,
                                "risk_tolerance": "medium",
                                "token_budget": {"daily": 50000, "per_cycle": 8000},
                            }
                        }
                    },
                )(),
            ):
                engine = AutonomyEngine(repo=None)
                engine.enabled = True
                engine.risk_tolerance = "medium"
                engine.autonomy_config = {
                    "enabled": True,
                    "risk_tolerance": "medium",
                    "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "throttle"},
                }
                report = engine.run_cycle(dry_run=True, max_steps=2)
            self.assertTrue(
                any("ledger:" in str(a) for a in report.actions_taken),
                msg=f"expected ledger lines in {report.actions_taken}",
            )
            self.assertGreaterEqual(len(list(base.glob("*.json"))), 1)

    def test_gate_block_writes_ledger(self):
        """#647: gate_high_impact shadow_required records durable provenance."""
        from plate_core.autonomy import AutonomyEngine
        from plate_core.ledger import list_decisions

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eng = AutonomyEngine(repo=None)
            eng.enabled = True
            eng.risk_tolerance = "low"
            eng.shadow_base_dir = root / "shadow"
            eng.checkpoint_base_dir = root / "cp"
            eng.ledger_base_dir = root / "ledger"
            eng.budget_base_dir = root / "budget"
            eng.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "low",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            blocked = eng.gate_high_impact("deploy", shadow_ack=None)
            self.assertTrue(blocked["blocked"])
            self.assertIn("ledger_id", blocked)
            rows = list_decisions(decision="shadow_required", base_dir=root / "ledger")
            self.assertGreaterEqual(len(rows), 1)
            self.assertEqual(rows[0].get("action_kind"), "deploy")

    def test_checkpoint_pause_writes_ledger(self):
        from plate_core.autonomy import AutonomyEngine
        from plate_core.checkpoint import create_checkpoint
        from plate_core.ledger import list_decisions

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_checkpoint(
                "block cycle",
                "need human",
                impact="high",
                base_dir=root / "cp",
            )
            eng = AutonomyEngine(repo=None)
            eng.enabled = True
            eng.risk_tolerance = "medium"
            eng.checkpoint_base_dir = root / "cp"
            eng.ledger_base_dir = root / "ledger"
            eng.budget_base_dir = root / "budget"
            eng.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "medium",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            report = eng.run_cycle(dry_run=True, max_steps=1)
            self.assertTrue(report.paused)
            self.assertTrue(any("ledger:" in str(a) for a in report.actions_taken))
            rows = list_decisions(decision="pause", base_dir=root / "ledger")
            self.assertGreaterEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
