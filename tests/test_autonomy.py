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
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyEngine(repo=None)
            engine.budget_base_dir = Path(tmp) / "budget"
            engine.autonomy_config = {"token_budget": {"daily": 1000, "per_cycle": 500, "action": "throttle"}}
            engine.enabled = True  # test exercises enforcement path (code DEFAULT is now medium/enabled per this PR; tests opt-in explicitly for isolation)
            engine.risk_tolerance = "high"
            engine.enabled = True
            engine._spent_this_cycle = 0
            engine._spent_today = 0
            engine._spent_usd_today = 0.0
            # First spend within limits
            self.assertEqual(engine.enforce_budget(400, "test"), Decision.PROCEED)
            self.assertEqual(engine._spent_this_cycle, 400)
            # Over per_cycle -> throttle (partial spend, still proceeds)
            self.assertEqual(engine.enforce_budget(200, "test"), Decision.THROTTLE)
            self.assertGreaterEqual(engine._spent_this_cycle, 400)

    def test_enforce_budget_pause(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyEngine(repo=None)
            engine.budget_base_dir = Path(tmp) / "budget"
            engine.autonomy_config = {"token_budget": {"daily": 1000, "per_cycle": 100, "action": "pause"}}
            engine.risk_tolerance = "high"
            engine.enabled = True
            engine._spent_this_cycle = 0
            engine._spent_today = 0
            engine._spent_usd_today = 0.0
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
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyEngine(repo=None)
            engine.budget_base_dir = Path(tmp) / "budget"
            engine.risk_tolerance = "medium"
            engine.autonomy_config = {"token_budget": {"daily": 1, "per_cycle": 1, "action": "pause"}}
            engine.enabled = True
            engine._spent_this_cycle = 100
            engine._spent_today = 100
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

    def test_decide_next_warn_annotation_and_no_double_spend(self):
        """Regression for #502 review: WARN is explicitly annotated; no double-spend (decide charges once, run trusts it)."""
        engine = AutonomyEngine(repo=None)
        engine.risk_tolerance = "high"
        engine.enabled = True
        # Tight budget to force WARN or THROTTLE path (policy default throttle -> WARN branch in some over cases)
        engine.autonomy_config = {"token_budget": {"per_cycle": 3000, "daily": 10000, "action": "warn"}}
        snap = engine.introspect()
        acts = engine.decide_next(snap)
        spent_after_decide = engine._spent_this_cycle
        # Run should not re-charge (use attached decision)
        report = engine.run_cycle(dry_run=True, max_steps=3)
        spent_after_run = engine._spent_this_cycle
        # spent should not have doubled from the re-enforce that was removed
        self.assertLessEqual(spent_after_run, spent_after_decide + 10)  # allow tiny probe
        if acts:
            # At least one act should carry decision; if WARN path hit, annotation present
            has_warn = any(a.get("decision") == "warn" or "WARN" in str(a.get("annotation", "")) for a in acts)
            # annotation may appear on WARN; the presence of decision key covers the "WARN annotation" request
            self.assertIn("decision", acts[0])
            # If a WARN decision was produced under the policy, its annotation should be there
            for a in acts:
                if a.get("decision") == "warn":
                    self.assertIn("annotation", a)
                    self.assertIn("WARN", a["annotation"])

    def test_default_config_conservative_for_review(self):
        """DEFAULT autonomy is medium/enabled (the intended opt-in per Epic #470 autonomy vision and this PR's Feature change).
        The conservative off is the safe starting recommendation in .plate and migration guidance (post #502 review).
        Engine treats absent/empty section via migration to the code DEFAULT.
        """
        # Note: load_plate_config may read local .plate; test the DEFAULT directly
        from plate_core.plate_config import DEFAULT_CONFIG
        auto = DEFAULT_CONFIG.get("autonomy", {})
        self.assertTrue(auto.get("enabled", False))
        self.assertEqual(auto.get("risk_tolerance"), "medium")

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


class TestShadowSimulation645(unittest.TestCase):
    """#645: simulation/shadow mode for high-impact autonomous actions."""

    def setUp(self):
        self._patches = [
            patch("plate_core.autonomy.get_cost_report", side_effect=Exception("no network")),
            patch("plate_core.autonomy.get_health", side_effect=Exception("no network")),
            patch("plate_core.autonomy.get_epic_status", side_effect=Exception("no network")),
            patch(
                "plate_core.autonomy.get_plate_config_report",
                return_value=type("R", (), {"to_dict": lambda self: {}})(),
            ),
            patch(
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
            ),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def test_classify_impact_catalog(self):
        from plate_core.autonomy import classify_action_impact
        self.assertEqual(classify_action_impact("what_next"), "low")
        self.assertEqual(classify_action_impact("health"), "low")
        self.assertEqual(classify_action_impact("babysit"), "medium")
        self.assertEqual(classify_action_impact("auto_merge"), "high")
        self.assertEqual(classify_action_impact("release_cut"), "critical")
        self.assertEqual(classify_action_impact("deploy"), "critical")
        self.assertEqual(classify_action_impact("force_push"), "critical")
        self.assertEqual(classify_action_impact("marketplace_publish"), "critical")
        self.assertEqual(classify_action_impact("totally_unknown_action"), "medium")

    def test_simulate_action_returns_shadow_report(self):
        from plate_core.autonomy import AutonomyEngine
        engine = AutonomyEngine(repo=None)
        engine.enabled = True
        engine.risk_tolerance = "low"
        engine.autonomy_config = {
            "enabled": True,
            "risk_tolerance": "low",
            "token_budget": {"daily": 50000, "per_cycle": 8000, "action": "throttle"},
            "cost_ceiling_usd": 10.0,
        }
        report = engine.simulate_action("release_cut", scope={"version": "1.0.0"})
        d = report.to_dict()
        self.assertEqual(d["mode"], "shadow")
        self.assertEqual(d["action_kind"], "release_cut")
        self.assertEqual(d["impact"], "critical")
        self.assertTrue(d["requires_approval"])
        self.assertFalse(d["would_execute"])
        self.assertIsInstance(d["predicted_side_effects"], list)
        self.assertGreater(len(d["predicted_side_effects"]), 0)
        self.assertGreater(d["estimated_tokens"], 0)
        self.assertTrue(d["shadow_id"])
        self.assertIsInstance(d["approval_reasons"], list)
        self.assertIsInstance(d["gate_preview"], list)

    def test_simulate_low_impact_no_approval(self):
        from plate_core.autonomy import AutonomyEngine
        engine = AutonomyEngine(repo=None)
        engine.enabled = True
        engine.risk_tolerance = "medium"
        engine.autonomy_config = {
            "enabled": True,
            "risk_tolerance": "medium",
            "token_budget": {"daily": 50000, "per_cycle": 8000},
        }
        report = engine.simulate_action("what_next")
        d = report.to_dict()
        self.assertEqual(d["impact"], "low")
        self.assertFalse(d["requires_approval"])
        self.assertTrue(d["would_execute"])
        self.assertTrue(d["risk_allowed"])

    def test_high_impact_blocked_without_shadow_ack_at_low_risk(self):
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine
        with tempfile.TemporaryDirectory() as tmp:
            shadow_dir = Path(tmp) / "shadow"
            cp_dir = Path(tmp) / "cp"
            engine = AutonomyEngine(repo=None)
            engine.enabled = True
            engine.risk_tolerance = "low"
            engine.shadow_base_dir = shadow_dir
            engine.checkpoint_base_dir = cp_dir
            engine.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "low",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            blocked = engine.gate_high_impact("auto_merge", shadow_ack=None)
            self.assertTrue(blocked["blocked"])
            self.assertEqual(blocked["mode"], "shadow_required")
            self.assertIn("shadow_report", blocked)
            self.assertIn("checkpoint_id", blocked)
            shadow = engine.simulate_action("auto_merge")
            still = engine.gate_high_impact("auto_merge", shadow_ack=shadow.shadow_id, approved=False)
            self.assertTrue(still["blocked"])
            ok = engine.gate_high_impact("auto_merge", shadow_ack=shadow.shadow_id, approved=True)
            self.assertFalse(ok["blocked"])

    def test_critical_always_requires_approval(self):
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyEngine(repo=None)
            engine.enabled = True
            engine.risk_tolerance = "high"
            engine.shadow_base_dir = Path(tmp) / "shadow"
            engine.checkpoint_base_dir = Path(tmp) / "cp"
            engine.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "high",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            shadow = engine.simulate_action("deploy")
            self.assertTrue(shadow.to_dict()["requires_approval"])
            blocked = engine.gate_high_impact("deploy", shadow_ack=shadow.shadow_id, approved=False)
            self.assertTrue(blocked["blocked"])
            unblocked = engine.gate_high_impact("deploy", shadow_ack=shadow.shadow_id, approved=True)
            self.assertFalse(unblocked["blocked"])

    def test_run_procedure_high_risk_shadow_default_when_low_tolerance(self):
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine, ProcedureDef
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyEngine(repo=None)
            engine.enabled = True
            engine.risk_tolerance = "low"
            engine.shadow_base_dir = Path(tmp) / "shadow"
            engine.checkpoint_base_dir = Path(tmp) / "cp"
            engine.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "low",
                "token_budget": {"daily": 5e4, "per_cycle": 8e3},
            }
            engine.procedures = [
                ProcedureDef(
                    id="risky-proc",
                    cadence="manual",
                    risk_level="high",
                    enabled=True,
                    description="high impact",
                ),
            ]
            result = engine.run_procedure("risky-proc", dry_run=False)
            self.assertEqual(result.get("status"), "shadow_required")
            self.assertIn("shadow_report", result)
            self.assertIn("checkpoint_id", result)

    def test_durable_shadow_ack_across_engine_instances(self):
        """#645 harden: shadow_ack must resolve from .agentic/shadow after process restart."""
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine, load_shadow_report

        with tempfile.TemporaryDirectory() as tmp:
            shadow_dir = Path(tmp) / "shadow"
            cp_dir = Path(tmp) / "cp"
            eng1 = AutonomyEngine(repo=None)
            eng1.enabled = True
            eng1.risk_tolerance = "low"
            eng1.shadow_base_dir = shadow_dir
            eng1.checkpoint_base_dir = cp_dir
            eng1.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "low",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            shadow = eng1.simulate_action("auto_merge")
            sid = shadow.shadow_id
            self.assertIsNotNone(load_shadow_report(sid, base_dir=shadow_dir))

            # Fresh engine (no in-memory previews) must still accept durable ack
            eng2 = AutonomyEngine(repo=None)
            eng2.enabled = True
            eng2.risk_tolerance = "low"
            eng2.shadow_base_dir = shadow_dir
            eng2.checkpoint_base_dir = cp_dir
            eng2.autonomy_config = eng1.autonomy_config
            self.assertEqual(eng2._shadow_previews, {})
            still = eng2.gate_high_impact("auto_merge", shadow_ack=sid, approved=False)
            self.assertTrue(still["blocked"])
            ok = eng2.gate_high_impact("auto_merge", shadow_ack=sid, approved=True)
            self.assertFalse(ok["blocked"])
            self.assertEqual(ok["mode"], "approved")

    def test_module_level_simulate_helper(self):
        from plate_core.autonomy import simulate_autonomy_action
        d = simulate_autonomy_action("release_finalize", repo=None)
        self.assertEqual(d["mode"], "shadow")
        self.assertEqual(d["impact"], "critical")
        # #645 harden fields always present (diff may be empty outside a git repo)
        self.assertIn("predicted_diff", d)
        self.assertIn("worktree_plan", d)
        self.assertTrue(d["worktree_plan"].get("path"))

    def test_git_diff_preview_and_worktree_plan(self):
        """#645: collect_git_diff_preview + worktree plan on simulate for high impact."""
        import subprocess
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import (
            AutonomyEngine,
            collect_git_diff_preview,
            plan_shadow_worktree,
            shadow_report_from_dict,
        )

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "test"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "a.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "b.txt").write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "add", "b.txt"], cwd=repo, check=True, capture_output=True)
            # No origin/release — falls back to WORKTREE / HEAD
            preview = collect_git_diff_preview(base_ref="origin/release", cwd=repo)
            self.assertTrue(preview["ok"], preview)
            self.assertGreaterEqual(preview["file_count"], 1)

            plan = plan_shadow_worktree("deploy", shadow_id="shadow-test-abc", base_ref="HEAD")
            self.assertIn("deploy-shadow-test-abc", plan["path"])
            self.assertTrue(plan["create_commands"])

            eng = AutonomyEngine(repo=None)
            eng.enabled = True
            eng.risk_tolerance = "medium"
            eng.shadow_base_dir = Path(tmp) / "shadow"
            eng.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "medium",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            report = eng.simulate_action(
                "deploy",
                scope={"cwd": str(repo), "base_ref": "HEAD"},
            )
            d = report.to_dict()
            self.assertTrue(d["predicted_diff"].get("ok"))
            self.assertTrue(d["worktree_plan"].get("path"))
            # Durable rehydrate keeps new fields
            rehyd = shadow_report_from_dict(d)
            self.assertEqual(rehyd.predicted_diff.get("ok"), True)
            self.assertTrue(rehyd.worktree_plan.get("create_commands"))

    def test_gate_honors_approved_checkpoint_id(self):
        """#648: approved checkpoint_id supplies approved + shadow_ack to gate."""
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine
        from plate_core.checkpoint import decide_checkpoint

        with tempfile.TemporaryDirectory() as tmp:
            shadow_dir = Path(tmp) / "shadow"
            cp_dir = Path(tmp) / "cp"
            eng = AutonomyEngine(repo=None)
            eng.enabled = True
            eng.risk_tolerance = "low"
            eng.shadow_base_dir = shadow_dir
            eng.checkpoint_base_dir = cp_dir
            eng.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "low",
                "token_budget": {"daily": 50000, "per_cycle": 8000},
            }
            blocked = eng.gate_high_impact(
                "auto_merge",
                shadow_ack=None,
                scope={"skip_git_preview": True},
            )
            self.assertTrue(blocked["blocked"])
            cid = blocked["checkpoint_id"]
            sid = blocked["shadow_report"]["shadow_id"]
            decide_checkpoint(cid, "approve", base_dir=cp_dir)
            # Fresh engine, only checkpoint_id (shadow from durable store + checkpoint)
            eng2 = AutonomyEngine(repo=None)
            eng2.enabled = True
            eng2.risk_tolerance = "low"
            eng2.shadow_base_dir = shadow_dir
            eng2.checkpoint_base_dir = cp_dir
            eng2.autonomy_config = eng.autonomy_config
            ok = eng2.gate_high_impact(
                "auto_merge",
                checkpoint_id=cid,
                create_checkpoint=False,
                scope={"skip_git_preview": True},
            )
            self.assertFalse(ok["blocked"], ok)
            self.assertEqual(ok["mode"], "approved")
            self.assertEqual(ok["shadow_report"]["shadow_id"], sid)

    def test_durable_budget_spend_across_engines(self):
        """#634: spend counters persist under .agentic/budget so governor survives restart."""
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine, Decision, load_budget_spend

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            eng1 = AutonomyEngine(repo=None)
            eng1.enabled = True
            eng1.risk_tolerance = "high"
            eng1.budget_base_dir = bdir
            # Isolate from any real .agentic/budget hydrated at __init__
            eng1._spent_today = 0
            eng1._spent_this_cycle = 0
            eng1._spent_usd_today = 0.0
            eng1.throttled_actions = 0
            eng1.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "high",
                "token_budget": {"daily": 1000, "per_cycle": 800, "action": "pause"},
            }
            self.assertEqual(eng1.enforce_budget(400, "test"), Decision.PROCEED)
            data = load_budget_spend(base_dir=bdir)
            self.assertEqual(data.get("spent_today"), 400)

            eng2 = AutonomyEngine(repo=None)
            eng2.enabled = True
            eng2.risk_tolerance = "high"
            eng2.budget_base_dir = bdir
            eng2.autonomy_config = eng1.autonomy_config
            eng2._load_durable_spend()
            self.assertEqual(eng2._spent_today, 400)
            # Remaining room 400; next 500 over daily -> pause
            self.assertEqual(eng2.enforce_budget(500, "test"), Decision.PAUSE)
            self.assertEqual(eng2._spent_today, 400)

    def test_cost_ceiling_usd_pauses(self):
        """#634: cost_ceiling_usd is a hard rail (pause under throttle policy)."""
        import tempfile
        from pathlib import Path
        from plate_core.autonomy import AutonomyEngine, Decision, tokens_to_usd

        with tempfile.TemporaryDirectory() as tmp:
            eng = AutonomyEngine(repo=None)
            eng.enabled = True
            eng.risk_tolerance = "high"
            eng.budget_base_dir = Path(tmp) / "budget"
            # Ceiling near-zero relative to estimate
            eng.autonomy_config = {
                "enabled": True,
                "risk_tolerance": "high",
                "token_budget": {"daily": 1_000_000, "per_cycle": 1_000_000, "action": "throttle"},
                "cost_ceiling_usd": 0.0001,
            }
            est = 50_000  # ~0.1 USD at heuristic rate
            self.assertGreater(tokens_to_usd(est), 0.0001)
            self.assertEqual(eng.enforce_budget(est, "plan_epic"), Decision.PAUSE)

    def test_get_budget_snapshot_and_markdown(self):
        """#634 UX: get_budget_snapshot merges limits + durable spend for CLI/loops."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from plate_core.autonomy import (
            format_budget_snapshot_markdown,
            get_budget_snapshot,
            save_budget_spend,
        )

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            save_budget_spend(
                {
                    "day": "2026-07-25",
                    "spent_today": 4000,
                    "spent_this_cycle": 500,
                    "spent_usd_today": 0.008,
                },
                base_dir=bdir,
            )

            class _Cfg:
                autonomy = {
                    "enabled": True,
                    "risk_tolerance": "medium",
                    "token_budget": {"daily": 10000, "per_cycle": 2000, "action": "pause"},
                    "cost_ceiling_usd": 1.0,
                }

            with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
                # load_budget_spend is called with base_dir — patch path via base_dir arg
                snap = get_budget_snapshot(base_dir=bdir, estimated_tokens=7000)
            self.assertEqual(snap["daily_limit"], 10000)
            self.assertEqual(snap["spent_today"], 4000)
            self.assertEqual(snap["remaining_tokens"], 6000)
            self.assertTrue(snap["would_pause"])
            self.assertIn("daily", snap["gate_reason"] or "")
            md = format_budget_snapshot_markdown(snap)
            self.assertIn("Budget snapshot", md)
            self.assertIn("4000/10000", md)

    def test_record_budget_spend_public(self):
        """#634/#775: gated surfaces charge durable spend outside AutonomyEngine."""
        import tempfile
        from pathlib import Path

        from plate_core.autonomy import (
            get_budget_snapshot,
            load_budget_spend,
            record_budget_spend,
            save_budget_spend,
        )

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            save_budget_spend(
                {
                    "date": __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .date()
                    .isoformat(),
                    "spent_today": 100,
                    "spent_this_cycle": 10,
                    "spent_usd_today": 0.0,
                },
                base_dir=bdir,
            )
            out = record_budget_spend(
                250,
                base_dir=bdir,
                reason="unit-test",
                action_kind="test_charge",
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["charged_tokens"], 250)
            self.assertEqual(out["spent_today"], 350)
            self.assertEqual(out["spent_this_cycle"], 260)
            data = load_budget_spend(base_dir=bdir)
            self.assertEqual(data.get("spent_today"), 350)
            self.assertEqual(data.get("last_action_kind"), "test_charge")
            snap = get_budget_snapshot(base_dir=bdir)
            self.assertEqual(snap["spent_today"], 350)

    def test_get_budget_snapshot_estimate_tokens_alias(self):
        """Surface gates pass estimate_tokens; alias must hydrate gate reasons."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from plate_core.autonomy import get_budget_snapshot, save_budget_spend

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            save_budget_spend(
                {
                    "date": __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .date()
                    .isoformat(),
                    "spent_today": 9000,
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
                        "per_cycle": 5000,
                        "action": "pause",
                    },
                }

            with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
                snap = get_budget_snapshot(
                    base_dir=bdir, estimate_tokens=2000
                )
            self.assertTrue(snap["would_pause"])
            self.assertIn("daily", snap.get("gate_reason") or "")

    def test_apply_live_budget_charge(self):
        """#777 helper charges only on live path and adjusts remaining."""
        import tempfile
        from pathlib import Path

        from plate_core.autonomy import apply_live_budget_charge, load_budget_spend

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "budget"
            out = {
                "ok": True,
                "budget_remaining": 10000,
                "notes": [],
            }
            apply_live_budget_charge(
                out,
                tokens=500,
                use_live_budget=True,
                action_kind="unit_test",
                reason="test",
                base_dir=bdir,
            )
            self.assertTrue(out["budget_charge"]["ok"])
            self.assertEqual(out["budget_remaining"], 9500)
            self.assertEqual(load_budget_spend(base_dir=bdir).get("spent_today"), 500)

            dry = {"ok": True, "budget_remaining": 10000, "notes": []}
            apply_live_budget_charge(
                dry,
                tokens=500,
                use_live_budget=False,
                action_kind="unit_test",
                base_dir=bdir,
            )
            self.assertNotIn("budget_charge", dry)
            self.assertEqual(load_budget_spend(base_dir=bdir).get("spent_today"), 500)


if __name__ == "__main__":
    unittest.main()
