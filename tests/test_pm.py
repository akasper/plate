"""Tests for Project Manager / Orchestrator (#660) — core + durable loop deepen."""

from __future__ import annotations

import json
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

    def test_get_status_zeros_prior_day_spend(self):
        """PM must not report critical pressure from yesterday's spend.json (#634/#660)."""
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            # Simulate get_budget_snapshot after UTC day rollover (spent zeroed).
            with patch(
                "plate_core.autonomy.get_budget_snapshot",
                return_value={
                    "spent_today": 0,
                    "spent_this_cycle": 0,
                    "daily_limit": 50000,
                    "per_cycle_limit": 8000,
                    "remaining_tokens": 50000,
                    "budget_pressure": "ok",
                    "burn_rate": 0.0,
                    "would_pause": False,
                },
            ):
                st = pm.get_status()
            self.assertEqual(st.budget_pressure, "ok")
            self.assertEqual(st.spent_today_durable, 0)
            self.assertEqual(st.budget_remaining_tokens, 50000)
            self.assertFalse(st.would_pause_next_cycle)

    def test_get_status_honors_budget_base_dir(self):
        """Isolated budget_base_dir must drive PM pressure, not operator spend (#634/#660)."""
        from plate_core.autonomy import save_budget_spend

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bdir = root / "budget"
            today = (
                __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .date()
                .isoformat()
            )
            save_budget_spend(
                {
                    "date": today,
                    "spent_today": 9999,
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

            pm = ProjectManager(
                repo=None,
                state_dir=root / "pm",
                budget_base_dir=bdir,
            )
            with patch("plate_core.autonomy.load_plate_config", return_value=_Cfg()):
                st = pm.get_status()
            self.assertLessEqual(int(st.budget_remaining_tokens or 0), 1)
            self.assertIn(st.budget_pressure, ("critical", "exhausted", "high"))
            self.assertEqual(st.spent_today_durable, 9999)

    def test_get_status_ignores_stale_spend_file_without_snapshot_patch(self):
        """Integration: stale prior-day spend.json must not make pressure critical."""
        with tempfile.TemporaryDirectory() as tmp:
            spend_path = Path(tmp) / "spend.json"
            spend_path.write_text(
                json.dumps(
                    {
                        "date": "2020-01-01",
                        "spent_today": 939804,
                        "spent_this_cycle": 321809,
                        "spent_usd_today": 1.88,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def _load_spend(*, base_dir=None):
                return json.loads(spend_path.read_text(encoding="utf-8"))

            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch("plate_core.autonomy.load_budget_spend", side_effect=_load_spend):
                # Real get_budget_snapshot + patched load → prior day zeros
                st = pm.get_status()
            self.assertEqual(st.spent_today_durable, 0)
            self.assertEqual(st.budget_remaining_tokens, 50000)
            self.assertEqual(st.budget_pressure, "ok")
            self.assertLess(st.burn_rate, 80.0)

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
                budget_remaining=100_000,
                record_ledger=False,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["loop_kind"], "bug")
            self.assertTrue(out["run_id"])

    def test_dispatch_loop_from_assignment_research_artifact(self):
        """#660: design/research PM work opens a #632 pending artifact proposal."""
        from plate_core.design_research_approval import get_proposal
        from plate_core.pm import dispatch_loop_from_assignment

        with tempfile.TemporaryDirectory() as tmp:
            adir = Path(tmp) / "artifacts"
            out = dispatch_loop_from_assignment(
                {
                    "work_type": "research",
                    "work_title": "Survey competitor onboarding",
                    "work_id": "issue-42",
                    "number": 42,
                    "risk": "low",
                    "risk_tolerance": "medium",
                    "packet": {"summary": "Compare install friction metrics."},
                },
                artifact_base_dir=adir,
                budget_remaining=100_000,
                record_ledger=False,
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["loop_kind"], "artifact")
            self.assertTrue(out["run_id"])
            self.assertEqual(out["stage"], "pending")
            prop = get_proposal(out["run_id"], base_dir=adir)
            self.assertIsNotNone(prop)
            self.assertEqual(prop["kind"], "research")
            self.assertEqual(prop["related_issue"], 42)

    def test_tick_artifact_assignment_completes_on_approve(self):
        """#660 tick path: approved artifact completes the PM assignment."""
        from plate_core.design_research_approval import decide_proposal, propose_artifact
        from plate_core.pm import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            pm_dir = Path(tmp) / "pm"
            adir = Path(tmp) / "artifacts"
            prop = propose_artifact(
                "design",
                "Wireframes for feed",
                "Rough layout for endless Q+Task feed",
                related_issue=7,
                base_dir=adir,
                use_live_budget=False,
                budget_remaining=100_000,
            )
            self.assertTrue(prop.get("ok"), prop)
            pid = prop["id"]
            decide_proposal(pid, "approve", decided_by="test", base_dir=adir)
            pm = ProjectManager(
                repo=None,
                state_dir=pm_dir,
                artifact_base_dir=adir,
                dispatch_fleet=False,
                dispatch_loops=False,
            )
            pm._assignments = [
                {
                    "assignment_id": "asg-art1",
                    "work_id": "7",
                    "work_title": "Wireframes for feed",
                    "work_type": "design",
                    "status": "delegated",
                    "loop_run_id": pid,
                    "loop_kind": "artifact",
                    "packet": {},
                }
            ]
            pm._save_queue()
            ticks = pm.tick_delegated_loops(dry_run=False, complete_when_done=True)
            self.assertEqual(len(ticks), 1)
            self.assertTrue(ticks[0]["completed_assignment"])
            self.assertEqual(pm._assignments[0]["status"], "done")
            self.assertEqual(pm._assignments[0]["loop_stage"], "approved")

    def test_tick_delegated_loops_completes_when_done(self):
        from plate_core.bug_loop import start_bug_loop, update_bug_loop
        from plate_core.pm import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            pm_dir = Path(tmp) / "pm"
            bdir = Path(tmp) / "bugs"
            started = start_bug_loop(
                bug_number=7,
                bug_title="done soon",
                risk="low",
                use_live_budget=False,
                base_dir=bdir,
                record_ledger=False,
            )
            rid = started["run"]["id"]
            update_bug_loop(rid, stage="done", status="done", base_dir=bdir)
            pm = ProjectManager(
                repo=None,
                state_dir=pm_dir,
                bug_loop_base_dir=bdir,
                dispatch_loops=False,
                dispatch_fleet=False,
            )
            pm._assignments = [
                {
                    "assignment_id": "asg-tick1",
                    "work_id": "7",
                    "work_title": "done soon",
                    "work_type": "bugfix",
                    "status": "delegated",
                    "loop_run_id": rid,
                    "loop_kind": "bug",
                    "packet": {},
                }
            ]
            ticks = pm.tick_delegated_loops(dry_run=True, complete_when_done=True)
            self.assertEqual(len(ticks), 1)
            self.assertTrue(ticks[0]["completed_assignment"])
            self.assertEqual(pm._assignments[0]["status"], "done")
            self.assertEqual(pm._assignments[0]["loop_stage"], "done")

    def test_run_cycle_includes_loop_ticks(self):
        from plate_core.feature_loop import start_feature_loop

        with tempfile.TemporaryDirectory() as tmp:
            pm_dir = Path(tmp) / "pm"
            fdir = Path(tmp) / "feats"
            started = start_feature_loop(
                feature_number=3,
                feature_title="tick me",
                risk="low",
                size="trivial",
                needs_media_approval=False,
                use_live_budget=False,
                base_dir=fdir,
                record_ledger=False,
            )
            rid = started["run"]["id"]
            pm = ProjectManager(
                repo=None,
                state_dir=pm_dir,
                feature_loop_base_dir=fdir,
                dispatch_fleet=False,
                dispatch_loops=False,
            )
            pm._assignments = [
                {
                    "assignment_id": "asg-tick2",
                    "work_id": "3",
                    "work_title": "tick me",
                    "work_type": "implement",
                    "status": "delegated",
                    "loop_run_id": rid,
                    "loop_kind": "feature",
                    "packet": {},
                }
            ]
            with patch.object(pm, "get_status", return_value=self._fake_status()), patch.object(
                pm, "collect_work", return_value=[]
            ):
                rep = pm.run_cycle(dry_run=True, max_assignments=1, tick_loops=True)
            self.assertIn("loop_ticks", rep)
            self.assertGreaterEqual(len(rep["loop_ticks"]), 1)
            self.assertEqual(rep["loop_ticks"][0]["loop_run_id"], rid)
            self.assertEqual(rep["loop_ticks"][0]["stage"], "estimate_cost")

    def test_tick_pm_loops_surface_advances_estimate(self):
        from plate_core.feature_loop import start_feature_loop
        from plate_core.pm import tick_pm_loops

        with tempfile.TemporaryDirectory() as tmp:
            pm_dir = Path(tmp) / "pm"
            fdir = Path(tmp) / "feats"
            started = start_feature_loop(
                feature_number=4,
                feature_title="tick surface",
                risk="low",
                size="trivial",
                needs_media_approval=False,
                use_live_budget=False,
                base_dir=fdir,
                record_ledger=False,
            )
            rid = started["run"]["id"]
            # seed queue via ProjectManager
            pm = ProjectManager(
                repo=None,
                state_dir=pm_dir,
                feature_loop_base_dir=fdir,
            )
            pm._assignments = [
                {
                    "assignment_id": "asg-tick3",
                    "work_id": "4",
                    "work_title": "tick surface",
                    "work_type": "implement",
                    "status": "delegated",
                    "loop_run_id": rid,
                    "loop_kind": "feature",
                    "packet": {},
                }
            ]
            pm._save_queue()
            out = tick_pm_loops(
                repo=None,
                dry_run=False,
                state_dir=pm_dir,
                feature_loop_base_dir=fdir,
            )
            self.assertTrue(out["ok"])
            self.assertGreaterEqual(out["n_ticks"], 1)
            self.assertGreaterEqual(out["n_advanced"], 1)
            self.assertEqual(out["loop_ticks"][0]["stage"], "plan")


if __name__ == "__main__":
    unittest.main()
