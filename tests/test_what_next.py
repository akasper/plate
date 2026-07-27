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

    def test_epic_when_healthy_pm_idle(self):
        """#905/#915: empty pipeline + idle PM + no closeout cands → stub refine, not PM."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"open_checkpoints": 0, "delegated": 0, "proposed": 0, "queue_size": 0},
            epic_closeout_candidates=[],
        )
        self.assertEqual(out["priority"], "epic")
        self.assertIn("refine", out["next_action"].lower())
        self.assertIn("no first-slice closeout candidates", out["next_action"].lower())
        self.assertNotIn("Project Manager cycle", out["next_action"])

    def test_empty_closeout_candidates_prefer_stub_refine(self):
        """#915: after #913 filters, empty candidates must not lead with closeout prose."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 20},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"queue_size": 0, "open_assignments": 0},
            epic_closeout_candidates=[],
        )
        self.assertEqual(out["priority"], "epic")
        self.assertIn("stub", out["next_action"].lower())
        self.assertNotIn("first-slice closeout for complete-child", out["next_action"])
        self.assertIn("915", out["rationale"])

    def test_pm_when_active_queue_even_with_open_epics(self):
        """Active PM queue still ranks PM over generic epic prose (#660)."""
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"open_checkpoints": 0, "delegated": 0, "proposed": 0, "queue_size": 2},
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
        # #905: idle PM + open epics → epic closeout/refine (not forced PM dry-run)
        self.assertEqual(out["priority"], "epic")
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


class TestWhatNextCompoundPriorityLadder(unittest.TestCase):
    """Proves: compound empty-pipeline ranking ladder for plate_what_next (#919/#364).

    Claim (AGENTS / agent_guidance what_next order): budget_gate beats open PR;
    open PR beats ready Feature; ready beats PM; PM active beats epic; named
    closeout when candidates present; empty candidates → stub refine (#915).
    Unit-level compound proof — Playwright babysit/release e2e still deferred.
    """

    _healthy = {"label_coverage_ok": True, "open_epic_count": 8}
    _budget_ok = {
        "budget_pressure": "ok",
        "remaining_tokens": 40000,
        "daily_limit": 50000,
        "risk_tolerance": "off",
    }

    def test_compound_priority_ladder_order(self):
        cases = [
            (
                "budget_gate",
                {
                    "budget": {
                        "budget_pressure": "exhausted",
                        "remaining_tokens": 0,
                        "daily_limit": 50000,
                    },
                    "open_prs": [{"number": 1, "title": "pr", "baseRefName": "release"}],
                    "ready_issues": [{"number": 2, "title": "feat", "labels": ["Feature"]}],
                    "pm_status": {"queue_size": 3, "delegated": 1},
                },
            ),
            (
                "open_pr",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [{"number": 10, "title": "in flight", "baseRefName": "release"}],
                    "ready_issues": [{"number": 11, "title": "ready", "labels": ["Feature"]}],
                    "pm_status": {"queue_size": 2, "delegated": 1},
                },
            ),
            (
                "ready_issue",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [],
                    "ready_issues": [
                        {"number": 20, "title": "ready feat", "labels": ["Feature"]}
                    ],
                    "pm_status": {"queue_size": 2, "delegated": 1},
                },
            ),
            (
                "pm_tick",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [],
                    "ready_issues": [],
                    "pm_status": {
                        "open_checkpoints": 0,
                        "delegated": 2,
                        "proposed": 0,
                        "queue_size": 2,
                    },
                },
            ),
            (
                "pm",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [],
                    "ready_issues": [],
                    "pm_status": {
                        "open_checkpoints": 0,
                        "delegated": 0,
                        "proposed": 0,
                        "queue_size": 2,
                        "open_assignments": 2,
                    },
                },
            ),
            (
                "epic",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [],
                    "ready_issues": [],
                    "pm_status": {"queue_size": 0, "open_assignments": 0},
                    "epic_closeout_candidates": [
                        {
                            "number": 656,
                            "title": "feed",
                            "children_total": 6,
                            "children_completed": 6,
                        }
                    ],
                },
            ),
            (
                "epic",
                {
                    "budget": dict(self._budget_ok),
                    "open_prs": [],
                    "ready_issues": [],
                    "pm_status": {"queue_size": 0},
                    "epic_closeout_candidates": [],
                },
            ),
        ]
        seen: list[str] = []
        for expected, kwargs in cases:
            out = recommend_what_next(health=dict(self._healthy), **kwargs)
            self.assertEqual(
                out["priority"],
                expected,
                msg=f"ladder step failed for expected={expected} got={out['priority']} action={out['next_action'][:80]}",
            )
            seen.append(out["priority"])
        # Last epic step with empty candidates must be stub-refine prose
        last = recommend_what_next(
            health=dict(self._healthy),
            budget=dict(self._budget_ok),
            open_prs=[],
            ready_issues=[],
            pm_status={"queue_size": 0},
            epic_closeout_candidates=[],
        )
        self.assertIn("stub", last["next_action"].lower())
        self.assertEqual(
            seen,
            ["budget_gate", "open_pr", "ready_issue", "pm_tick", "pm", "epic", "epic"],
        )


class TestEpicCloseoutCandidates(unittest.TestCase):
    """Proves: complete-child open Epics are named on idle epic priority (#909)."""

    def test_recommend_names_closeout_candidates(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 12},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"queue_size": 0, "open_assignments": 0, "open_checkpoints": 0},
            epic_closeout_candidates=[
                {
                    "number": 656,
                    "title": "Q&A planning",
                    "children_total": 6,
                    "children_completed": 6,
                },
                {
                    "number": 657,
                    "title": "Autonomy foundations",
                    "children_total": 5,
                    "children_completed": 5,
                },
            ],
        )
        self.assertEqual(out["priority"], "epic")
        self.assertIn("#656", out["next_action"])
        self.assertIn("#657", out["next_action"])
        self.assertEqual(out["state_snapshot"]["epic_closeout_candidate_count"], 2)
        self.assertEqual(len(out["epic_closeout_candidates"]), 2)
        self.assertEqual(out["epic_closeout_candidates"][0]["number"], 656)

    def test_fetch_filters_incomplete_empty_and_implemented(self):
        from plate_core.what_next import fetch_epic_closeout_candidates

        class FakeGh:
            def api(self, endpoint, method="GET", fields=None, retries=3, base_backoff=0.5):
                return {
                    "data": {
                        "repository": {
                            "issues": {
                                "nodes": [
                                    {
                                        "number": 656,
                                        "title": "done kids already implemented",
                                        "labels": {
                                            "nodes": [
                                                {"name": "Epic"},
                                                {"name": "status:implemented"},
                                            ]
                                        },
                                        "subIssuesSummary": {"total": 6, "completed": 6},
                                    },
                                    {
                                        "number": 350,
                                        "title": "done kids need closeout",
                                        "labels": {"nodes": [{"name": "Epic"}]},
                                        "subIssuesSummary": {"total": 3, "completed": 3},
                                    },
                                    {
                                        "number": 661,
                                        "title": "still open kids",
                                        "labels": {"nodes": [{"name": "Epic"}]},
                                        "subIssuesSummary": {"total": 2, "completed": 1},
                                    },
                                    {
                                        "number": 999,
                                        "title": "empty stub epic",
                                        "labels": {"nodes": [{"name": "Epic"}]},
                                        "subIssuesSummary": {"total": 0, "completed": 0},
                                    },
                                ]
                            }
                        }
                    }
                }

        out = fetch_epic_closeout_candidates("akasper/plate", gh=FakeGh())
        nums = [c["number"] for c in out]
        self.assertEqual(nums, [350])
        self.assertEqual(out[0]["children_total"], 3)

    def test_fetch_degrades_on_api_error(self):
        from plate_core.what_next import fetch_epic_closeout_candidates

        class BoomGh:
            def api(self, *a, **k):
                raise RuntimeError("rate limit")

        self.assertEqual(fetch_epic_closeout_candidates("akasper/plate", gh=BoomGh()), [])


class TestGetWhatNextLiveWiring(unittest.TestCase):
    """Proves: live get_what_next wires PM status into idle vs active ranking (#907/#905/#364).

    Claim: empty pipeline + idle PM queue does not force PM dry-run solely from open
    epics; active open_assignments/queue_size still ranks PM (#660).
    """

    def _health(self, *, open_epics: int = 5):
        class H:
            def to_dict(self):
                return {
                    "label_coverage_ok": True,
                    "open_epic_count": open_epics,
                    "budget_pressure": "ok",
                    "budget_remaining_tokens": 50000,
                    "budget_daily_limit": 50000,
                    "budget_risk_tolerance": "off",
                }

        return H()

    def test_get_what_next_idle_pm_ranks_epic_not_pm(self):
        from unittest.mock import patch

        from plate_core.what_next import get_what_next

        idle_pm = {
            "open_checkpoints": 0,
            "delegated": 0,
            "proposed": 0,
            "queue_size": 0,
            "open_assignments": 0,
            "budget_pressure": "ok",
            "risk_tolerance": "off",
        }
        with patch("plate_core.health.get_health", return_value=self._health()):
            with patch("plate_core.autonomy.get_budget_snapshot", return_value={
                "budget_pressure": "ok",
                "remaining_tokens": 50000,
                "daily_limit": 50000,
                "risk_tolerance": "off",
            }):
                with patch("plate_core.what_next.fetch_ready_issue_candidates", return_value=[]):
                    with patch("plate_core.pm.get_pm_status", return_value=idle_pm):
                        with patch("plate_core.release.get_release_status", side_effect=Exception("skip")):
                            with patch("plate_core.release.collect_fragments", return_value=[]):
                                out = get_what_next(
                                    "akasper/plate",
                                    include_prs=False,
                                    include_fragments=True,
                                    include_ready_issues=True,
                                    include_pm=True,
                                    include_release=True,
                                )
        self.assertEqual(out["priority"], "epic")
        self.assertIn("closeout", out["next_action"].lower())
        self.assertEqual(out["state_snapshot"]["pm_queue_size"], 0)

    def test_get_what_next_open_assignments_ranks_pm(self):
        """Proves: open_assignments alone (even if queue_size omitted) ranks PM (#907)."""
        from unittest.mock import patch

        from plate_core.what_next import get_what_next, recommend_what_next

        # Pure recommend path: open_assignments without queue_size
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 3},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            pm_status={"open_checkpoints": 0, "delegated": 0, "proposed": 0, "open_assignments": 2},
        )
        self.assertEqual(out["priority"], "pm")
        self.assertIn("Project Manager", out["next_action"])

        active_pm = {
            "open_checkpoints": 0,
            "delegated": 1,
            "proposed": 1,
            "queue_size": 2,
            "open_assignments": 2,
            "budget_pressure": "ok",
            "risk_tolerance": "off",
        }
        with patch("plate_core.health.get_health", return_value=self._health()):
            with patch("plate_core.autonomy.get_budget_snapshot", return_value={
                "budget_pressure": "ok",
                "remaining_tokens": 50000,
                "daily_limit": 50000,
                "risk_tolerance": "off",
            }):
                with patch("plate_core.what_next.fetch_ready_issue_candidates", return_value=[]):
                    with patch("plate_core.pm.get_pm_status", return_value=active_pm):
                        with patch("plate_core.release.get_release_status", side_effect=Exception("skip")):
                            with patch("plate_core.release.collect_fragments", return_value=[]):
                                live = get_what_next(
                                    "akasper/plate",
                                    include_prs=False,
                                    include_fragments=True,
                                    include_ready_issues=True,
                                    include_pm=True,
                                    include_release=True,
                                )
        # Delegated > 0 ranks pm_tick before generic pm cycle
        self.assertEqual(live["priority"], "pm_tick")


class TestAdoptionWhatNext(unittest.TestCase):
    """Proves: adoption readiness ranks on what_next (#937 / #633)."""

    def test_adoption_not_ready_before_ready_issue(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 3},
            budget={
                "budget_pressure": "ok",
                "remaining_tokens": 40000,
                "daily_limit": 50000,
            },
            open_prs=[],
            ready_issues=[{"number": 100, "title": "Some feature"}],
            adoption={
                "core_ready": False,
                "estimated_minutes_remaining": 12,
                "within_30m_budget": True,
                "next_command": "gh plate import-payload --dry-run --strategy conservative --json",
            },
        )
        self.assertEqual(out["priority"], "adoption")
        self.assertIn("import-payload", out["next_action"])
        self.assertEqual(out["estimated_minutes_remaining"], 12)
        self.assertFalse(out["state_snapshot"]["adoption_core_ready"])

    def test_open_pr_beats_adoption(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 1},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[{"number": 50, "title": "x", "baseRefName": "release"}],
            adoption={"core_ready": False, "estimated_minutes_remaining": 20, "next_command": "x"},
        )
        self.assertEqual(out["priority"], "open_pr")

    def test_core_ready_skips_adoption(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[{"number": 200, "title": "Ready feat"}],
            adoption={"core_ready": True, "estimated_minutes_remaining": 0},
            pm_status={"queue_size": 0},
        )
        self.assertEqual(out["priority"], "ready_issue")
        self.assertTrue(out["state_snapshot"]["adoption_core_ready"])


class TestScheduledOpsWhatNext(unittest.TestCase):
    """Proves: scheduled ops rank on what_next (#933 / #659)."""

    def test_active_scheduled_op_after_ready_before_pm(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 5},
            budget={
                "budget_pressure": "ok",
                "remaining_tokens": 40000,
                "daily_limit": 50000,
                "risk_tolerance": "off",
            },
            open_prs=[],
            ready_issues=[],
            pm_status={"open_checkpoints": 2, "delegated": 1, "queue_size": 3},
            scheduled_ops={
                "active_runs": [
                    {"op_id": "release-cut-prep", "status": "blocked"},
                ],
                "runnable_at_tolerance": [],
            },
        )
        self.assertEqual(out["priority"], "scheduled_op")
        self.assertEqual(out["op_id"], "release-cut-prep")
        self.assertIn("release-cut-prep", out["next_action"])
        self.assertEqual(out["state_snapshot"]["scheduled_ops_active_count"], 1)

    def test_open_pr_still_beats_active_scheduled_op(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 1},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[{"number": 99, "title": "x", "baseRefName": "release"}],
            scheduled_ops={
                "active_runs": [{"op_id": "release-cut-prep", "status": "running"}],
            },
        )
        self.assertEqual(out["priority"], "open_pr")

    def test_runnable_scheduled_ops_plan_when_pm_idle(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 10},
            budget={
                "budget_pressure": "ok",
                "remaining_tokens": 40000,
                "daily_limit": 50000,
                "risk_tolerance": "medium",
            },
            open_prs=[],
            ready_issues=[],
            pm_status={"open_checkpoints": 0, "delegated": 0, "proposed": 0, "queue_size": 0},
            epic_closeout_candidates=[],
            scheduled_ops={
                "active_runs": [],
                "runnable_at_tolerance": [
                    {"id": "scheduled-refactor", "risk_level": "low"},
                    {"id": "release-cut-prep", "risk_level": "medium"},
                ],
            },
        )
        self.assertEqual(out["priority"], "scheduled_ops_plan")
        self.assertEqual(out["op_id"], "scheduled-refactor")
        self.assertIn("dry-run", out["next_action"].lower())
        self.assertEqual(out["state_snapshot"]["scheduled_ops_runnable_count"], 2)

    def test_ready_issue_beats_runnable_scheduled_ops(self):
        out = recommend_what_next(
            health={"label_coverage_ok": True, "open_epic_count": 2},
            budget={"budget_pressure": "ok", "remaining_tokens": 40000, "daily_limit": 50000},
            open_prs=[],
            ready_issues=[{"number": 933, "title": "Rank scheduled ops"}],
            pm_status={"queue_size": 0},
            scheduled_ops={
                "runnable_at_tolerance": [{"id": "scheduled-refactor", "risk_level": "low"}],
            },
        )
        self.assertEqual(out["priority"], "ready_issue")
        self.assertEqual(out["issue_number"], 933)


if __name__ == "__main__":
    unittest.main()
