"""Tests for Project Manager / Orchestrator (#660) — core + durable loop deepen."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.pm import (
    ProjectManager,
    assign_work,
    build_assignment_tui,
    classify_work_type,
    get_persona,
    list_team,
    pick_agent,
    pm_feed_items,
)


class TestPMTeamAndAssign(unittest.TestCase):
    def test_team_has_core_personas(self):
        team = list_team()
        ids = {p["id"] for p in team}
        self.assertIn("dev-cautious", ids)
        self.assertIn("design-minimal", ids)
        self.assertIn("research-analyst", ids)
        self.assertIn("release-engineer", ids)
        self.assertGreaterEqual(len(team), 6)

    def test_classify_and_pick(self):
        self.assertEqual(classify_work_type({"item_type": "question"}), "qanda")
        self.assertEqual(classify_work_type({"title": "Fix crash"}), "bugfix")
        self.assertEqual(classify_work_type({"title": "Release cut"}), "release")
        agent = pick_agent("refactor", "medium")
        self.assertEqual(agent["id"], "dev-refactorer")
        cautious = pick_agent("implement", "low")
        self.assertEqual(cautious["id"], "dev-cautious")

    def test_assign_budget_block(self):
        asg = assign_work(
            {"id": "1", "title": "Implement feature X", "item_type": "feature", "impact": "medium"},
            risk_tolerance="medium",
            budget_remaining=100,
        )
        self.assertEqual(asg["status"], "blocked")
        self.assertIn("budget", asg["rationale"])

    def test_assign_ok(self):
        asg = assign_work(
            {"id": "2", "title": "Implement feature Y", "type": "feature", "impact": "medium"},
            risk_tolerance="medium",
            budget_remaining=50000,
        )
        self.assertEqual(asg["work_type"], "implement")
        self.assertIn(asg["status"], ("proposed", "delegated"))
        self.assertTrue(asg["agent_id"].startswith("dev-"))
        self.assertIn("packet", asg)
        self.assertIn("ask_user_question", asg)
        self.assertIn("options", asg["ask_user_question"])

    def test_release_requires_checkpoint(self):
        asg = assign_work(
            {"title": "Cut release v1", "impact": "high"},
            risk_tolerance="high",
            budget_remaining=50000,
        )
        self.assertTrue(asg["requires_checkpoint"])

    def test_assign_opens_checkpoint_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            asg = assign_work(
                {"id": "hi", "title": "Cut release v2", "impact": "high"},
                risk_tolerance="high",
                budget_remaining=50000,
                open_checkpoint=True,
                checkpoint_base_dir=Path(tmp),
            )
            self.assertTrue(asg.get("checkpoint_id"))
            self.assertTrue(asg["checkpoint_id"].startswith("cp-"))
            self.assertTrue(list(Path(tmp).glob("cp-*.json")))

    def test_tui_payload_shape(self):
        tui = build_assignment_tui(
            {
                "assignment_id": "asg-1",
                "work_title": "Ship feature",
                "agent_name": "Cautious",
                "status": "proposed",
            }
        )
        self.assertIn("question", tui)
        self.assertGreaterEqual(len(tui["options"]), 3)


class TestPMCycle(unittest.TestCase):
    def _fake_status(self, **overrides):
        base = {
            "to_dict": lambda self: {
                "enabled": True,
                "risk_tolerance": "medium",
                "budget_remaining_tokens": 50000,
                "open_checkpoints": 0,
                "budget_pressure": "ok",
                "would_pause_next_cycle": False,
            },
            "open_checkpoints": 0,
            "risk_tolerance": "medium",
            "budget_remaining_tokens": 50000,
            "enabled": True,
            "burn_rate": 0.0,
            "autopilot_score": 50,
            "team_size": 8,
            "open_assignments": 0,
            "last_cycle": None,
            "queue_size": 0,
            "proposed": 0,
            "delegated": 0,
            "blocked": 0,
            "done": 0,
            "budget_pressure": "ok",
            "would_pause_next_cycle": False,
            "spent_today_durable": None,
        }
        base.update(overrides)
        return type("S", (), base)()

    def test_run_cycle_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm,
                "collect_work",
                return_value=[
                    {"id": "w1", "title": "Implement auth", "type": "feature", "impact": "medium"},
                    {"id": "w2", "title": "Research competitors", "type": "research", "impact": "low"},
                ],
            ):
                report = pm.run_cycle(dry_run=True, max_assignments=2)
            self.assertEqual(report["status"], "completed")
            self.assertEqual(len(report["assignments"]), 2)
            self.assertTrue(report["dry_run"])
            self.assertTrue((Path(tmp) / "last_cycle.json").exists())
            self.assertTrue((Path(tmp) / "queue.json").exists())
            # durable queue reload
            pm2 = ProjectManager(repo=None, state_dir=Path(tmp))
            q = pm2.list_queue()
            self.assertEqual(len(q), 2)
            self.assertIn("ask_user_question", q[0])

    def test_paused_on_checkpoints(self):
        pm = ProjectManager(repo=None)
        with patch.object(
            pm,
            "get_status",
            return_value=self._fake_status(
                open_checkpoints=1,
                to_dict=lambda self: {"open_checkpoints": 1},
            ),
        ):
            report = pm.run_cycle(dry_run=True)
        self.assertEqual(report["status"], "paused")

    def test_dedupe_existing_work_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm,
                "collect_work",
                return_value=[
                    {"id": "w1", "title": "Implement auth", "type": "feature", "impact": "medium"},
                ],
            ):
                pm.run_cycle(dry_run=True, max_assignments=5)
                r2 = pm.run_cycle(dry_run=True, max_assignments=5)
            # second cycle should not re-add same work_id
            self.assertEqual(len(r2["assignments"]), 0)
            self.assertEqual(len(pm.list_queue()), 1)

    def test_complete_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm,
                "collect_work",
                return_value=[{"id": "w9", "title": "Do thing", "type": "feature"}],
            ):
                rep = pm.run_cycle(dry_run=True)
            aid = rep["assignments"][0]["assignment_id"]
            out = pm.complete_assignment(aid, status="done", note="shipped")
            self.assertTrue(out["ok"])
            self.assertEqual(out["assignment"]["status"], "done")
            st = pm.get_status()
            # get_status without patch uses real checkpoint count 0 + queue
            self.assertEqual(st.done, 1)

    def test_run_loop_stops_on_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            calls = {"n": 0}

            def collect(limit=10):
                calls["n"] += 1
                if calls["n"] == 1:
                    return [{"id": "once", "title": "One shot", "type": "feature"}]
                return []

            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm, "collect_work", side_effect=collect
            ):
                loop = pm.run_loop(max_cycles=5, dry_run=True, max_assignments=3)
            self.assertGreaterEqual(loop["n_cycles"], 1)
            self.assertIn(loop["stopped_reason"], ("idle", "max_cycles"))
            self.assertIn("queue", loop)

    def test_get_status_counts_pending_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp_pm, tempfile.TemporaryDirectory() as tmp_cp:
            from plate_core.checkpoint import create_checkpoint

            create_checkpoint(
                title="Need human",
                reason="test",
                impact="high",
                risk_tolerance="off",
                base_dir=Path(tmp_cp),
            )
            pm = ProjectManager(
                repo=None,
                state_dir=Path(tmp_pm),
                checkpoint_base_dir=Path(tmp_cp),
            )
            st = pm.get_status()
            self.assertGreaterEqual(st.open_checkpoints, 1)

    def test_paused_on_budget_pressure(self):
        pm = ProjectManager(repo=None)
        with patch.object(
            pm,
            "get_status",
            return_value=self._fake_status(
                enabled=True,
                risk_tolerance="medium",
                budget_pressure="critical",
                would_pause_next_cycle=True,
                budget_remaining_tokens=100,
                to_dict=lambda self: {
                    "enabled": True,
                    "risk_tolerance": "medium",
                    "budget_pressure": "critical",
                    "budget_remaining_tokens": 100,
                },
            ),
        ):
            report = pm.run_cycle(dry_run=True)
        self.assertEqual(report["status"], "paused")
        self.assertEqual(report.get("pause_kind"), "budget")

    def test_pm_feed_items_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm,
                "collect_work",
                return_value=[{"id": "w-feed", "title": "Feature Z", "type": "feature"}],
            ):
                pm.run_cycle(dry_run=True)
            # force blocked row
            pm._assignments[0]["status"] = "blocked"
            pm._save_queue()
            items = pm_feed_items(state_dir=Path(tmp))
            types = {i.get("item_type") for i in items}
            self.assertIn("pm_assignment", types)

    def test_apply_cycle_dispatches_fleet_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm_dir = Path(tmp) / "pm"
            fleet_dir = Path(tmp) / "fleet"
            feat_dir = Path(tmp) / "featloops"
            pm = ProjectManager(
                repo=None,
                state_dir=pm_dir,
                fleet_base_dir=fleet_dir,
                feature_loop_base_dir=feat_dir,
                dispatch_fleet=True,
                dispatch_loops=True,
            )
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm,
                "collect_work",
                return_value=[
                    {
                        "id": "w-fleet",
                        "title": "Implement feature fleet",
                        "type": "feature",
                        "impact": "medium",
                        "number": 42,
                    }
                ],
            ), patch("plate_core.baseline_catalog.delegate_to_agent", create=True):
                rep = pm.run_cycle(
                    dry_run=False, max_assignments=1, dispatch_fleet=True, dispatch_loops=True
                )
            self.assertEqual(rep["status"], "completed")
            self.assertTrue(rep.get("dispatch_fleet"))
            self.assertGreaterEqual(len(rep.get("fleet_handoffs") or []), 1)
            asg = rep["assignments"][0]
            self.assertEqual(asg["status"], "delegated")
            self.assertTrue(asg.get("fleet_handoff_id"))
            from plate_core.fleet import list_handoffs

            hos = list_handoffs(status="all", base_dir=fleet_dir)
            self.assertTrue(any(h.get("handoff_id") == asg["fleet_handoff_id"] for h in hos))
            # #660/#639: implement assignments also open a feature loop
            self.assertTrue(rep.get("dispatch_loops"))
            self.assertGreaterEqual(len(rep.get("loop_dispatches") or []), 1)
            self.assertEqual(asg.get("loop_kind"), "feature")
            self.assertTrue(asg.get("loop_run_id"))
            from plate_core.feature_loop import list_feature_loops

            loops = list_feature_loops(status="active", base_dir=feat_dir)
            self.assertTrue(any(r.get("id") == asg["loop_run_id"] for r in loops))

    def test_dispatch_loop_from_assignment_bugfix(self):
        from plate_core.pm import dispatch_loop_from_assignment

        with tempfile.TemporaryDirectory() as tmp:
            bdir = Path(tmp) / "bugloops"
            out = dispatch_loop_from_assignment(
                {
                    "work_type": "bugfix",
                    "work_title": "Fix labels flake",
                    "work_id": "issue-99",
                    "number": 99,
                    "risk": "low",
                    "risk_tolerance": "medium",
                },
                bug_loop_base_dir=bdir,
                record_ledger=False,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["loop_kind"], "bug")
            self.assertTrue(out["run_id"])


if __name__ == "__main__":
    unittest.main()
