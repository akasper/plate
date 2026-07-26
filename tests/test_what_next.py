"""Tests for hardened plate_what_next (#789 / #654)."""

from __future__ import annotations

import unittest

from plate_core.what_next import recommend_what_next


class TestRecommendWhatNext(unittest.TestCase):
    def test_budget_critical_first(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={
                "budget_pressure": "exhausted",
                "remaining_tokens": 0,
                "daily_limit": 50000,
                "risk_tolerance": "off",
            },
            open_prs=[{"number": 1, "title": "x", "baseRefName": "release"}],
        )
        self.assertEqual(out["priority"], "budget_gate")
        self.assertIn("budget", out["next_action"].lower())
        self.assertEqual(out["state_snapshot"]["budget_pressure"], "exhausted")

    def test_budget_gate_on_would_pause_next_cycle_elevated(self):
        """#634: elevated pressure + next-cycle pause still ranks budget_gate first."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={
                "budget_pressure": "elevated",
                "remaining_tokens": 3000,
                "daily_limit": 10000,
                "would_pause_next_cycle": True,
                "risk_tolerance": "medium",
            },
            open_prs=[{"number": 1, "title": "x", "baseRefName": "release"}],
        )
        self.assertEqual(out["priority"], "budget_gate")
        self.assertTrue(out["state_snapshot"]["would_pause_next_cycle"])
        self.assertIn("would_pause", out["next_action"])

    def test_open_pr_before_epic(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 3},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[
                {
                    "number": 788,
                    "title": "Surface budget_gate",
                    "baseRefName": "release",
                }
            ],
        )
        self.assertEqual(out["priority"], "open_pr")
        self.assertIn("#788", out["next_action"])
        self.assertEqual(out["pr_number"], 788)

    def test_labels_bootstrap(self):
        out = recommend_what_next(
            health={"label_coverage_ok": False, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 50000},
            open_prs=[],
        )
        self.assertEqual(out["priority"], "bootstrap")

    def test_epic_when_healthy(self):
        """Empty pipeline + open epics prefer PM orchestrator (#660) over bare epic prose."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
        )
        self.assertEqual(out["priority"], "pm")
        self.assertIn("Project Manager", out["next_action"])

    def test_ready_issue_before_generic_epic(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[
                {"number": 793, "title": "what_next ready candidates", "labels": ["Feature"]},
                {"number": 331, "title": "config lifecycle", "labels": ["Feature"]},
            ],
        )
        self.assertEqual(out["priority"], "ready_issue")
        self.assertEqual(out["issue_number"], 793)
        self.assertIn("#793", out["next_action"])
        self.assertEqual(out["state_snapshot"]["ready_issue_count"], 2)
        self.assertEqual(len(out["ready_issues"]), 2)

    def test_spec_audit_actionable_before_ready_issue(self):
        """#340: actionable SPEC drift from health outranks ready Features."""
        out = recommend_what_next(
            health={
                "label_coverage_ok": True,
                "open_epic_count": 5,
                "spec_audit_status": "actionable",
                "spec_audit_actionable_count": 4,
                "spec_audit_next_step": "gh plate spec-audit --followups",
            },
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[{"number": 340, "title": "health surface", "labels": ["Feature"]}],
        )
        self.assertEqual(out["priority"], "spec_audit")
        self.assertIn("SPEC", out["next_action"])
        self.assertEqual(out["state_snapshot"]["spec_audit_actionable_count"], 4)

    def test_open_pr_still_beats_spec_audit(self):
        out = recommend_what_next(
            health={
                "label_coverage_ok": True,
                "open_epic_count": 2,
                "spec_audit_status": "actionable",
                "spec_audit_actionable_count": 3,
            },
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[{"number": 804, "title": "in flight", "baseRefName": "release"}],
        )
        self.assertEqual(out["priority"], "open_pr")

    def test_pm_checkpoint_before_cycle(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 3},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"open_checkpoints": 2, "delegated": 1, "queue_size": 3},
        )
        self.assertEqual(out["priority"], "pm_checkpoint")
        self.assertEqual(out["state_snapshot"]["pm_open_checkpoints"], 2)

    def test_pm_tick_when_delegated(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 1},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"open_checkpoints": 0, "delegated": 2, "proposed": 0, "queue_size": 2},
        )
        self.assertEqual(out["priority"], "pm_tick")
        self.assertIn("tick", out["next_action"])

    def test_pm_proposed_prefers_approve_run(self):
        """Proposed queue rows must route to status=run, not another dry-run assign (#892)."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={
                "open_checkpoints": 0,
                "delegated": 0,
                "proposed": 3,
                "queue_size": 3,
                "risk_tolerance": "off",
            },
        )
        self.assertEqual(out["priority"], "pm_propose_run")
        self.assertIn("approve", out["next_action"].lower())
        self.assertIn("status=run", out["prompt_segment"])

    def test_ready_issue_still_beats_pm(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[{"number": 793, "title": "ready", "labels": ["Feature"]}],
            pm_status={"open_checkpoints": 0, "delegated": 4, "queue_size": 4},
        )
        self.assertEqual(out["priority"], "ready_issue")

    def test_epic_fallback_without_pm_and_zero_epics_uses_fragments(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pending_fragment_count=3,
            pm_status={},
        )
        self.assertEqual(out["priority"], "fragments")

    def test_release_repair_when_tracks_missing(self):
        """#814: missing multi-track branches outrank SPEC/PM/epic."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5, "spec_audit_status": "ok"},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            release_status={
                "release_branch_mode": "legacy",
                "release_track_branches": {
                    "release": True,
                    "release-major": False,
                    "release-minor": False,
                    "release-patch": False,
                },
            },
        )
        self.assertEqual(out["priority"], "release_repair")
        self.assertIn("release-major", out["missing_release_tracks"])
        self.assertIn("repair", out["next_action"])

    def test_open_pr_beats_release_repair(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[{"number": 813, "title": "docs", "baseRefName": "release"}],
            release_status={
                "release_branch_mode": "legacy",
                "release_track_branches": {
                    "release": True,
                    "release-major": False,
                    "release-minor": False,
                    "release-patch": False,
                },
            },
        )
        self.assertEqual(out["priority"], "open_pr")

    def test_healthy_multi_track_skips_repair(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            release_status={
                "release_branch_mode": "multi-track",
                "release_track_branches": {
                    "release": True,
                    "release-major": True,
                    "release-minor": True,
                    "release-patch": True,
                },
            },
            pm_status={"open_checkpoints": 0, "delegated": 0, "queue_size": 0},
        )
        self.assertEqual(out["priority"], "pm")
        self.assertEqual(out["state_snapshot"]["missing_release_tracks"], [])

    def test_open_pr_still_beats_ready_issue(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[{"number": 800, "title": "in flight", "baseRefName": "release"}],
            ready_issues=[{"number": 793, "title": "ready", "labels": ["Feature"]}],
        )
        self.assertEqual(out["priority"], "open_pr")
        self.assertEqual(out["pr_number"], 800)

    def test_budget_still_beats_ready_issue(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={
                "budget_pressure": "critical",
                "remaining_tokens": 100,
                "daily_limit": 50000,
            },
            open_prs=[],
            ready_issues=[{"number": 793, "title": "ready", "labels": ["Feature"]}],
        )
        self.assertEqual(out["priority"], "budget_gate")

    def test_fragments_when_no_epics(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 0},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000},
            open_prs=[],
            pending_fragment_count=12,
        )
        self.assertEqual(out["priority"], "fragments")

    def test_fetch_ready_issue_candidates_filters(self):
        from plate_core.what_next import fetch_ready_issue_candidates

        class FakeGh:
            def api(self, endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                if "status:ready-to-work" in endpoint or "status%3Aready-to-work" in endpoint:
                    return {
                        "items": [
                            {
                                "number": 793,
                                "title": "ready one",
                                "labels": [{"name": "Feature"}, {"name": "status:ready-to-work"}],
                            },
                            {
                                "number": 999,
                                "title": "stub ready",
                                "labels": [
                                    {"name": "Feature"},
                                    {"name": "status:ready-to-work"},
                                    {"name": "status:stub"},
                                ],
                            },
                        ]
                    }
                return {
                    "items": [
                        {
                            "number": 340,
                            "title": "spec audit",
                            "labels": [{"name": "Feature"}],
                        },
                        {
                            "number": 453,
                            "title": "Licensing docs",
                            "labels": [{"name": "Documentation"}],
                        },
                        {
                            "number": 634,
                            "title": "budgets",
                            "labels": [
                                {"name": "Feature"},
                                {"name": "status:implemented"},
                            ],
                        },
                    ]
                }

        out = fetch_ready_issue_candidates("akasper/plate", limit=10, gh=FakeGh())
        nums = [i["number"] for i in out]
        self.assertIn(793, nums)
        self.assertIn(340, nums)
        self.assertIn(453, nums)  # Documentation is agent-actionable
        self.assertNotIn(999, nums)
        self.assertNotIn(634, nums)


class TestWhatNextCLI(unittest.TestCase):
    def test_cmd_what_next_json(self):
        import argparse
        import json
        from io import StringIO
        from unittest.mock import patch

        from plate_core import cli as cli_mod

        fake = {
            "next_action": "babysit open PR #1",
            "priority": "open_pr",
            "rationale": "test",
            "state_snapshot": {"open_pr_count": 1},
            "prompt_segment": "do it",
        }
        args = argparse.Namespace(
            repo="akasper/plate",
            agent_type="general",
            no_prs=True,
            no_budget=True,
            no_fragments=True,
            json=True,
        )
        buf = StringIO()
        # from .what_next import get_what_next binds name in cli_mod.cmd_what_next locals;
        # patch the module attribute before the call so the import loads the mock.
        with patch("plate_core.what_next.get_what_next", return_value=fake):
            with patch("sys.stdout", buf):
                rc = cli_mod.cmd_what_next(args)
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["priority"], "open_pr")

    def test_parser_registers_what_next(self):
        from plate_core.cli import build_parser

        help_text = build_parser().format_help()
        self.assertIn("what-next", help_text)


if __name__ == "__main__":
    unittest.main()
