"""Tests for shared branch policy (#1448 / #1449)."""

from __future__ import annotations

import unittest

from plate_core.branch_policy import (
    evaluate_full_branch_policy,
    evaluate_integration_branch_policy,
    is_valid_epic_base_for_head,
)
from plate_core.pr_integration_base_gate import run_gate
from plate_core.pr_main_source_gate import run_gate as run_main_source_gate
from plate_core.release import probe_remote_branch
from plate_core.pr_gates_checks import resolve_integration_base, resolve_expected_integration_base


class BranchPolicyTests(unittest.TestCase):
    def test_feature_into_main_rejected(self):
        failures = evaluate_full_branch_policy(
            base="main",
            head="cursor/feature-foo",
            labels=["Feature", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={
                "release-minor": True,
                "release-major": True,
                "release-patch": True,
            },
        )
        ids = [f.check_id for f in failures]
        self.assertIn("main_source", ids)

    def test_release_label_does_not_authorize_feature_head_to_main(self):
        failures = evaluate_full_branch_policy(
            base="main",
            head="cursor/feature-foo",
            labels=["Feature", "Release", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
        )
        self.assertTrue(any(f.check_id == "main_source" for f in failures))

    def test_valid_release_head_into_main(self):
        failures = evaluate_full_branch_policy(
            base="main",
            head="release-v1.0.0",
            labels=["Release", "Documentation"],
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
        )
        self.assertEqual(failures, [])

    def test_wrong_release_track_rejected(self):
        failures = evaluate_integration_branch_policy(
            base="release-patch",
            head="cursor/feature",
            labels=["Feature", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={
                "release-minor": True,
                "release-major": True,
                "release-patch": True,
            },
        )
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].check_id, "base_branch")
        self.assertIn("release-minor", failures[0].message)

    def test_minor_label_targets_release_minor(self):
        failures = evaluate_integration_branch_policy(
            base="release-minor",
            head="cursor/feature",
            labels=["Feature", "Minor", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={
                "release-minor": True,
                "release-major": True,
                "release-patch": True,
            },
        )
        self.assertEqual(failures, [])

    def test_epic_base_valid_for_same_epic_head(self):
        self.assertTrue(
            is_valid_epic_base_for_head("epic/demo", "epic/demo/feature-login")
        )
        failures = evaluate_integration_branch_policy(
            base="epic/demo",
            head="epic/demo/feature-login",
            labels=["Feature", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
        )
        self.assertEqual(failures, [])

    def test_epic_base_rejects_unrelated_head(self):
        failures = evaluate_integration_branch_policy(
            base="epic/demo",
            head="cursor/other",
            labels=["Feature", "area:agent"],
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
        )
        self.assertEqual(len(failures), 1)

    def test_major_label_missing_branch_errors_not_fallback(self):
        res = resolve_integration_base(
            release_branch_mode="multi-track",
            release_track_branches={
                "release-minor": True,
                "release-major": False,
                "release-patch": True,
            },
            pr_labels=["Feature"],
            issue_labels=["Major"],
        )
        self.assertIsNone(res.expected)
        self.assertIn("release-major", res.error or "")

    def test_major_on_issue_labels_matches_preflight(self):
        res = resolve_integration_base(
            release_branch_mode="multi-track",
            release_track_branches={
                "release-minor": True,
                "release-major": True,
                "release-patch": True,
            },
            pr_labels=["Feature"],
            issue_labels=["Major"],
        )
        self.assertEqual(res.expected, "release-major")

    def test_no_release_branches_fail_closed(self):
        res = resolve_integration_base(
            release_branch_mode="none",
            release_track_branches={},
            pr_labels=["Feature"],
        )
        self.assertIsNone(res.expected)
        self.assertTrue(res.error)
        failures = evaluate_integration_branch_policy(
            base="release-minor",
            head="cursor/x",
            labels=["Feature", "area:agent"],
            release_branch_mode="none",
            release_track_branches={},
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("bootstrap", failures[0].message.lower())

    def test_legacy_release_base_passes(self):
        failures = evaluate_integration_branch_policy(
            base="release",
            head="cursor/feature",
            labels=["Feature", "area:agent"],
            release_branch_mode="legacy",
            release_track_branches={"release": True},
        )
        self.assertEqual(failures, [])

    def test_feedback_response_skips_integration_policy(self):
        failures = evaluate_integration_branch_policy(
            base="main",
            head="chore",
            labels=["Feedback Response"],
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
        )
        self.assertEqual(failures, [])

    def test_integration_gate_cli(self):
        status = (
            '{"release_branch_mode":"multi-track",'
            '"release_track_branches":{"release-minor":true,"release-major":true,"release-patch":true}}'
        )
        self.assertEqual(
            run_gate(
                base="release-minor",
                head="cursor/x",
                labels=["Feature", "area:agent"],
                repo=None,
                release_status_json=status,
            ),
            0,
        )
        self.assertEqual(
            run_gate(
                base="main",
                head="cursor/x",
                labels=["Feature"],
                repo=None,
                release_status_json=status,
            ),
            0,
        )
        self.assertEqual(
            run_gate(
                base="release-patch",
                head="cursor/x",
                labels=["Feature", "area:agent"],
                repo=None,
                release_status_json=status,
            ),
            1,
        )

    def test_main_source_cli_unchanged(self):
        self.assertEqual(run_main_source_gate(base="main", head="release", labels=["Release"]), 0)
        self.assertEqual(run_main_source_gate(base="main", head="cursor/x", labels=["Feature"]), 1)

    def test_probe_branch_404_vs_api_error(self):
        from plate_core.github_client import GhApiError

        class _Gh:
            def __init__(self, mode: str):
                self.mode = mode

            def api(self, _endpoint: str):
                if self.mode == "404":
                    raise GhApiError("gh: Not Found (HTTP 404)")
                raise GhApiError("gh: Resource not accessible (HTTP 403)")

        exists, err = probe_remote_branch(_Gh("403"), "o/r", "release-minor")  # type: ignore[arg-type]
        self.assertIsNone(exists)
        self.assertIn("403", err or "")

        exists, err = probe_remote_branch(_Gh("404"), "o/r", "release-minor")  # type: ignore[arg-type]
        self.assertFalse(exists)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
