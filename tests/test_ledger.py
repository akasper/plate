"""Tests for provenance + decision ledger (#647)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.ledger import (
    format_ledger_summary_markdown,
    get_decision,
    ledger_feed_items,
    ledger_summary,
    list_blocking_decisions,
    list_decisions,
    list_spend_intervals,
    query_decisions,
    record_decision,
    record_from_autonomy_action,
    record_jev_score,
    record_spend_interval,
    render_decision_marker,
    spend_interval_has_jev_score,
    sum_spend_interval_tokens,
    validate_ledger_entry,
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
        self.assertEqual(s["blocking_count"], 1)
        self.assertIsNotNone(s["last_blocking"])
        self.assertIn("b", s["by_action_kind"])
        md = format_ledger_summary_markdown(s)
        self.assertIn("Blocking", md)
        self.assertIn("Decision ledger", md)

    def test_blocking_and_feed_items(self):
        record_decision("what_next", "proceed", "ok", base_dir=self.base)
        rec = record_decision(
            "deploy",
            "shadow_required",
            "need human",
            shadow_id="shadow-xyz",
            checkpoint_id="cp-abc",
            related_issue=647,
            impact="critical",
            base_dir=self.base,
        )
        blocked = list_blocking_decisions(base_dir=self.base)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["id"], rec["id"])
        feed = ledger_feed_items(base_dir=self.base)
        self.assertEqual(len(feed), 1)
        item = feed[0]
        self.assertEqual(item["type"], "ledger_gate")
        self.assertEqual(item["id"], rec["id"])
        self.assertTrue(item["ask_user_question"]["options"])
        labels = {o["id"] for o in item["ask_user_question"]["options"]}
        self.assertIn("decide_checkpoint", labels)
        self.assertIn("resume_shadow", labels)
        self.assertIn("inspect", labels)


class TestSpendLedger1352(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "ledger"
        self.base.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_legacy_decision_json_loads_without_record_type(self):
        legacy = {
            "id": "dec-legacy001",
            "action_kind": "what_next",
            "decision": "proceed",
            "reason": "ok",
            "sources": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        path = self.base / "dec-legacy001.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")
        got = get_decision("dec-legacy001", base_dir=self.base)
        self.assertIsNotNone(got)
        self.assertEqual(got["action_kind"], "what_next")
        rows = list_decisions(base_dir=self.base)
        self.assertEqual(len(rows), 1)
        spend_rows = list_spend_intervals(base_dir=self.base)
        self.assertEqual(spend_rows, [])

    def test_record_spend_interval_and_list(self):
        out = record_spend_interval(
            run_id="run-a",
            cloud_agent_id="bc-agent-1",
            parent_run_id="coord-9",
            lifecycle_task_type="marketing_copy",
            model="composer-2.5",
            tier="T2",
            effort="low",
            route_clarity="clear",
            input_tokens=100,
            output_tokens=40,
            cached_read_tokens=10,
            tool_output_tokens=5,
            turns=3,
            handoff_packet_size=1200,
            handoff_packet_unit="tokens",
            rediscovery_count=1,
            outcome_accepted=True,
            cost_usd=0.12,
            base_dir=self.base,
        )
        self.assertTrue(out["id"].startswith("spend-"))
        self.assertEqual(sum_spend_interval_tokens(out), 155)
        rows = list_spend_intervals(run_id="run-a", base_dir=self.base)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lifecycle_task_type"], "marketing_copy")
        self.assertNotIn(
            rows[0]["id"],
            {r.get("id") for r in list_decisions(base_dir=self.base)},
        )

    def test_validate_rejects_bad_tier(self):
        with self.assertRaises(ValueError):
            record_spend_interval(tier="T9", base_dir=self.base)

    def test_validate_ledger_entry_normalizes_spend(self):
        normalized, errors = validate_ledger_entry(
            {
                "id": "spend-test",
                "record_type": "spend_interval",
                "tier": "t1",
                "route_clarity": "AMBIGUOUS",
                "input_tokens": "10",
            }
        )
        self.assertEqual(errors, [])
        self.assertEqual(normalized["tier"], "T1")
        self.assertEqual(normalized["route_clarity"], "ambiguous")
        self.assertEqual(normalized["input_tokens"], 10)

    def test_record_jev_score_shadow_fields(self):
        out = record_jev_score(
            run_id="run-jev-1",
            lifecycle_task_type="support_triage",
            jev_score=0.82,
            jev_suggested_tier="T1",
            jev_model="composer-2.5",
            jev_route_clarity="ambiguous",
            tier="T2",
            model="gpt-5.6-sol-high",
            route_clarity="clear",
            base_dir=self.base,
        )
        self.assertTrue(out["metadata"].get("jev_shadow_mode"))
        self.assertEqual(out["jev_score"], 0.82)
        self.assertEqual(out["jev_suggested_tier"], "T1")
        self.assertEqual(out["tier"], "T2")
        scored = list_spend_intervals(jev_scored=True, base_dir=self.base)
        self.assertEqual(len(scored), 1)
        self.assertTrue(spend_interval_has_jev_score(scored[0]))

    def test_record_jev_score_requires_run_identity(self):
        with self.assertRaises(ValueError):
            record_jev_score(jev_score=1.0, base_dir=self.base)

    def test_validate_rejects_bad_jev_tier(self):
        with self.assertRaises(ValueError):
            record_jev_score(
                run_id="r1",
                jev_score=0.5,
                jev_suggested_tier="T9",
                base_dir=self.base,
            )

    def test_spend_interval_can_carry_jev_on_same_row(self):
        out = record_spend_interval(
            run_id="run-combined",
            lifecycle_task_type="marketing_copy",
            tier="T2",
            cost_usd=0.05,
            jev_score=0.71,
            jev_suggested_tier="T2",
            base_dir=self.base,
        )
        self.assertEqual(out["cost_usd"], 0.05)
        self.assertEqual(out["jev_score"], 0.71)

    def test_spend_interval_metadata_tier_step(self):
        out = record_spend_interval(
            run_id="run-tier-step",
            tier="T1",
            metadata={"tier_step": "start"},
            base_dir=self.base,
        )
        self.assertEqual(out["metadata"]["tier_step"], "start")
        out2 = record_spend_interval(
            run_id="run-tier-step-2",
            tier="T2",
            metadata={"tier_step": "ESCALATED"},
            base_dir=self.base,
        )
        self.assertEqual(out2["metadata"]["tier_step"], "escalated")

    def test_validate_rejects_bad_tier_step(self):
        with self.assertRaises(ValueError) as ctx:
            record_spend_interval(
                metadata={"tier_step": "retry"},
                base_dir=self.base,
            )
        self.assertIn("tier_step", str(ctx.exception))


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
