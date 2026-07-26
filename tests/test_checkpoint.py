"""Tests for unified checkpoint / approval primitive (#648)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.checkpoint import (
    checkpoint_approval_for_gate,
    CheckpointStatus,
    autonomy_is_paused_by_checkpoints,
    create_checkpoint,
    create_checkpoint_for_shadow,
    decide_checkpoint,
    get_checkpoint,
    list_checkpoints,
    list_open_checkpoints,
    should_auto_approve,
)


class TestCheckpoint648(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "checkpoints"
        self.base.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_pending_medium_impact(self):
        out = create_checkpoint(
            "Approve design",
            "Need human judgment on design doc",
            impact="medium",
            action_kind="plan_epic",
            related_issue=648,
            base_dir=self.base,
        )
        self.assertEqual(out["status"], CheckpointStatus.PENDING.value)
        self.assertTrue(out["pause_autonomy"])
        self.assertIn("id", out)
        self.assertTrue((self.base / f"{out['id']}.json").exists())
        self.assertIn("PLATE-CHECKPOINT:BEGIN", out["marker"])

    def test_auto_approve_low_impact_medium_risk(self):
        self.assertTrue(should_auto_approve("low", "medium", enabled=True))
        self.assertFalse(should_auto_approve("low", "low", enabled=True))
        self.assertFalse(should_auto_approve("high", "high", enabled=True))
        self.assertFalse(should_auto_approve("critical", "high", enabled=True))
        self.assertFalse(should_auto_approve("low", "medium", enabled=False))

        out = create_checkpoint(
            "Cheap health nudge",
            "informational only",
            impact="low",
            risk_tolerance="medium",
            autonomy_enabled=True,
            base_dir=self.base,
        )
        self.assertEqual(out["status"], CheckpointStatus.AUTO_APPROVED.value)
        self.assertTrue(out["auto_approved"])
        self.assertFalse(out["pause_autonomy"])

    def test_decide_approve_and_list_open(self):
        out = create_checkpoint(
            "Ship release",
            "release cut needs approval",
            impact="critical",
            action_kind="release_cut",
            base_dir=self.base,
        )
        cid = out["id"]
        open_list = list_open_checkpoints(base_dir=self.base)
        self.assertEqual(len(open_list), 1)
        self.assertEqual(open_list[0]["id"], cid)

        decided = decide_checkpoint(cid, "approve", decided_by="human", note="LGTM", base_dir=self.base)
        self.assertTrue(decided["ok"])
        self.assertEqual(decided["status"], CheckpointStatus.APPROVED.value)
        self.assertFalse(decided["pause_autonomy"])
        self.assertEqual(list_open_checkpoints(base_dir=self.base), [])

        got = get_checkpoint(cid, base_dir=self.base)
        self.assertEqual(got["decided_by"], "human")
        self.assertEqual(got["decision_note"], "LGTM")

    def test_decide_reject_and_double_decide(self):
        out = create_checkpoint("X", "y", impact="high", base_dir=self.base)
        cid = out["id"]
        rejected = decide_checkpoint(cid, "reject", decided_by="owner", base_dir=self.base)
        self.assertTrue(rejected["ok"])
        self.assertEqual(rejected["status"], CheckpointStatus.REJECTED.value)
        again = decide_checkpoint(cid, "approve", base_dir=self.base)
        self.assertFalse(again["ok"])

    def test_invalid_decision(self):
        out = create_checkpoint("X", "y", base_dir=self.base)
        bad = decide_checkpoint(out["id"], "maybe", base_dir=self.base)
        self.assertFalse(bad["ok"])

    def test_list_status_filter(self):
        create_checkpoint("a", "r", impact="high", base_dir=self.base)
        create_checkpoint(
            "b",
            "r",
            impact="low",
            risk_tolerance="high",
            autonomy_enabled=True,
            base_dir=self.base,
        )
        pending = list_checkpoints(status="pending", base_dir=self.base)
        auto = list_checkpoints(status="auto_approved", base_dir=self.base)
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(auto), 1)

    def test_shadow_bridge(self):
        shadow = {
            "action_kind": "deploy",
            "impact": "critical",
            "shadow_id": "shadow-deploy-1",
            "approval_reasons": ["critical impact always requires human"],
            "estimated_tokens": 8000,
            "estimated_cost_usd": 0.02,
            "predicted_side_effects": ["push to prod"],
            "gate_preview": ["human checkpoint"],
        }
        # Defaults risk=off / autonomy disabled → advisory (no pause freeze)
        cp = create_checkpoint_for_shadow(shadow, base_dir=self.base)
        self.assertEqual(cp["status"], CheckpointStatus.PENDING.value)
        self.assertEqual(cp["shadow_id"], "shadow-deploy-1")
        self.assertEqual(cp["action_kind"], "deploy")
        self.assertEqual(cp["impact"], "critical")
        self.assertFalse(cp.get("pause_autonomy"))
        self.assertEqual(list_open_checkpoints(base_dir=self.base), [])

    def test_shadow_bridge_pauses_when_autonomy_on(self):
        shadow = {
            "action_kind": "deploy",
            "impact": "critical",
            "shadow_id": "shadow-deploy-pause-1",
            "approval_reasons": ["critical impact always requires human"],
            "estimated_tokens": 8000,
            "estimated_cost_usd": 0.02,
            "predicted_side_effects": ["push to prod"],
            "gate_preview": ["human checkpoint"],
        }
        cp = create_checkpoint_for_shadow(
            shadow,
            risk_tolerance="low",
            autonomy_enabled=True,
            base_dir=self.base,
        )
        self.assertTrue(cp.get("pause_autonomy"))
        self.assertEqual(len(list_open_checkpoints(base_dir=self.base)), 1)

    def test_create_checkpoint_for_shadow_dedupes(self):
        from plate_core.checkpoint import find_open_checkpoint, list_open_checkpoints

        shadow = {
            "action_kind": "deploy",
            "impact": "critical",
            "shadow_id": "shadow-deploy-dedupe-a",
            "approval_reasons": ["critical impact always requires human"],
            "estimated_tokens": 8000,
            "estimated_cost_usd": 0.02,
            "predicted_side_effects": ["push to prod"],
            "gate_preview": ["human checkpoint"],
        }
        cp1 = create_checkpoint_for_shadow(
            shadow,
            risk_tolerance="low",
            autonomy_enabled=True,
            base_dir=self.base,
        )
        shadow2 = dict(shadow)
        shadow2["shadow_id"] = "shadow-deploy-dedupe-b"
        cp2 = create_checkpoint_for_shadow(
            shadow2,
            risk_tolerance="low",
            autonomy_enabled=True,
            base_dir=self.base,
        )
        self.assertEqual(cp1["id"], cp2["id"])
        self.assertTrue(cp2.get("deduped"))
        deploy = [
            c
            for c in list_open_checkpoints(base_dir=self.base)
            if c.get("action_kind") == "deploy"
        ]
        self.assertEqual(len(deploy), 1)
        found = find_open_checkpoint(action_kind="deploy", base_dir=self.base)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], cp1["id"])

    def test_create_checkpoint_for_shadow_dedupes_advisory(self):
        """risk=off shadow gates still dedupe pending advisory records."""
        shadow = {
            "action_kind": "deploy",
            "impact": "critical",
            "shadow_id": "shadow-deploy-adv-a",
            "approval_reasons": ["risk_tolerance=off"],
            "estimated_tokens": 1000,
            "estimated_cost_usd": 0.01,
            "predicted_side_effects": [],
            "gate_preview": [],
        }
        cp1 = create_checkpoint_for_shadow(shadow, base_dir=self.base)
        cp2 = create_checkpoint_for_shadow(shadow, base_dir=self.base)
        self.assertEqual(cp1["id"], cp2["id"])
        self.assertTrue(cp2.get("deduped"))
        self.assertFalse(cp1.get("pause_autonomy"))
        pending = [
            c
            for c in list_checkpoints(status="pending", base_dir=self.base)
            if c.get("action_kind") == "deploy"
        ]
        self.assertEqual(len(pending), 1)
        self.assertEqual(list_open_checkpoints(base_dir=self.base), [])

    def test_autonomy_paused_helper(self):
        create_checkpoint("block engine", "need approval", impact="high", base_dir=self.base)
        info = autonomy_is_paused_by_checkpoints(base_dir=self.base)
        self.assertTrue(info["paused"])
        self.assertGreaterEqual(info["open_count"], 1)




    def test_checkpoint_approval_for_gate(self):
        shadow = {
            "action_kind": "deploy",
            "impact": "critical",
            "shadow_id": "shadow-deploy-gate-1",
            "approval_reasons": ["critical"],
            "estimated_tokens": 1000,
            "estimated_cost_usd": 0.01,
            "predicted_side_effects": [],
            "gate_preview": [],
        }
        cp = create_checkpoint_for_shadow(shadow, base_dir=self.base)
        pending = checkpoint_approval_for_gate(cp["id"], action_kind="deploy", base_dir=self.base)
        self.assertFalse(pending["approved"])
        decided = decide_checkpoint(cp["id"], "approve", base_dir=self.base)
        self.assertTrue(decided["ok"])
        ok = checkpoint_approval_for_gate(cp["id"], action_kind="deploy", base_dir=self.base)
        self.assertTrue(ok["approved"])
        self.assertEqual(ok["shadow_id"], "shadow-deploy-gate-1")


class TestAutonomyCheckpointPause(unittest.TestCase):
    def test_run_cycle_pauses_on_open_checkpoint(self):
        from plate_core.autonomy import AutonomyEngine

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "cp"
            base.mkdir()
            create_checkpoint("pause me", "human required", impact="high", base_dir=base)
            with patch("plate_core.checkpoint.CHECKPOINT_DIR", base):
                with patch(
                    "plate_core.checkpoint._ensure_dir",
                    side_effect=lambda b=None: base if b is None else Path(b),
                ):
                    engine = AutonomyEngine(repo=None)
                    engine.enabled = True
                    engine.risk_tolerance = "medium"
                    engine.autonomy_config = {
                        "enabled": True,
                        "risk_tolerance": "medium",
                        "token_budget": {"daily": 50000, "per_cycle": 8000},
                    }
                    # Directly call with patched list via autonomy_is_paused
                    with patch(
                        "plate_core.checkpoint.autonomy_is_paused_by_checkpoints",
                        return_value={
                            "paused": True,
                            "open_count": 1,
                            "checkpoint_ids": ["cp-test"],
                            "titles": ["pause me"],
                        },
                    ):
                        report = engine.run_cycle(dry_run=True, max_steps=1)
            self.assertTrue(report.paused)
            self.assertEqual(report.status, "paused")
            self.assertTrue(any("checkpoint" in a for a in report.actions_taken))


if __name__ == "__main__":
    unittest.main()
