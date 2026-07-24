"""Tests for Project Manager / Orchestrator (#660) first slice."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plate_core.pm import (
    ProjectManager,
    assign_work,
    classify_work_type,
    get_persona,
    list_team,
    pick_agent,
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

    def test_release_requires_checkpoint(self):
        asg = assign_work(
            {"title": "Cut release v1", "impact": "high"},
            risk_tolerance="high",
            budget_remaining=50000,
        )
        self.assertTrue(asg["requires_checkpoint"])


class TestPMCycle(unittest.TestCase):
    def test_run_cycle_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectManager(repo=None, state_dir=Path(tmp))
            with patch.object(
                pm,
                "get_status",
                return_value=type(
                    "S",
                    (),
                    {
                        "to_dict": lambda self: {
                            "enabled": True,
                            "risk_tolerance": "medium",
                            "budget_remaining_tokens": 50000,
                            "open_checkpoints": 0,
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
                    },
                )(),
            ), patch.object(
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

    def test_paused_on_checkpoints(self):
        pm = ProjectManager(repo=None)
        with patch.object(
            pm,
            "get_status",
            return_value=type(
                "S",
                (),
                {
                    "to_dict": lambda self: {"open_checkpoints": 1},
                    "open_checkpoints": 1,
                    "risk_tolerance": "medium",
                    "budget_remaining_tokens": 50000,
                },
            )(),
        ):
            report = pm.run_cycle(dry_run=True)
        self.assertEqual(report["status"], "paused")


if __name__ == "__main__":
    unittest.main()
