"""Tests for gh plate pr preflight / pr create wrapper (#1418)."""

from __future__ import annotations

import unittest

import plate_core.pr_gates_payload as payload
import plate_core.pr_preflight as preflight
from plate_core.pr_gates_checks import (
    check_feature_release_fragment,
    check_pr_type_labels,
    check_strict_closing_keyword,
    closing_keyword_fix_message,
    run_preflight_gate_checks,
)


class PrPreflightGateTests(unittest.TestCase):
    def test_refs_only_body_fails_with_exact_fix_line(self):
        failure = check_strict_closing_keyword(
            "Refs #1418\n\nSummary",
            ["Feature"],
            owner="akasper",
            repo="plate",
        )
        self.assertIsNotNone(failure)
        self.assertEqual(
            failure.message,
            closing_keyword_fix_message(issue_number=1418),
        )

    def test_passing_feature_slice(self):
        failures = run_preflight_gate_checks(
            body="Closes #1418\n",
            labels=["Feature", "area:cli"],
            base="release",
            changed_paths=[".agentic/releases/unreleased/pr-preflight-1418.json"],
            owner="akasper",
            repo="plate",
            release_branch_mode="legacy",
            release_track_branches={"release": True},
        )
        self.assertEqual(failures, [])

    def test_preflight_and_payload_share_gate_functions(self):
        from plate_core.pr_gates_checks import issue_link_gate_failure_lines as checks_fn

        self.assertIs(preflight.run_preflight_gate_checks, run_preflight_gate_checks)
        self.assertIs(payload.issue_link_gate_failure_lines, checks_fn)

    def test_run_preflight_report_passes_with_injected_state(self):
        report = preflight.run_preflight(
            body="Closes #1418",
            labels=["Feature", "area:cli"],
            base="release",
            changed_paths=[".agentic/releases/unreleased/x.json"],
            repo="akasper/plate",
            release_status={
                "release_branch_mode": "legacy",
                "release_track_branches": {"release": True},
            },
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["expected_base"], "release")

    def test_missing_type_label_reports_create_fix(self):
        report = preflight.run_preflight(
            body="Closes #1",
            labels=[],
            base="release",
            changed_paths=[],
            repo="akasper/plate",
            release_status={
                "release_branch_mode": "legacy",
                "release_track_branches": {"release": True},
            },
        )
        self.assertFalse(report["passed"])
        messages = [item["message"] for item in report["failures"]]
        self.assertTrue(any("gh pr create --label" in msg for msg in messages))


class HardeningPrTypeTests(unittest.TestCase):
    def test_hardening_only_is_accepted(self):
        self.assertIsNone(check_pr_type_labels(["Hardening", "area:tests"]))

    def test_hardening_plus_feature_is_rejected(self):
        failure = check_pr_type_labels(["Hardening", "Feature"])
        self.assertIsNotNone(failure)
        self.assertIn("exactly one type label", failure.message)

    def test_hardening_plus_bug_is_rejected(self):
        failure = check_pr_type_labels(["Hardening", "Bug"])
        self.assertIsNotNone(failure)
        self.assertIn("exactly one type label", failure.message)

    def test_hardening_requires_release_fragment(self):
        failure = check_feature_release_fragment(["Hardening"], ["src/plate_core/x.py"])
        self.assertIsNotNone(failure)
        self.assertEqual(failure.check_id, "release_fragment")

    def test_hardening_with_fragment_passes(self):
        self.assertIsNone(
            check_feature_release_fragment(
                ["Hardening"],
                [".agentic/releases/unreleased/hardening-1456.json"],
            )
        )

    def test_hardening_requires_closing_keyword(self):
        failure = check_strict_closing_keyword(
            "Refs #1456\n",
            ["Hardening"],
            owner="akasper",
            repo="plate",
        )
        self.assertIsNotNone(failure)
        self.assertEqual(failure.check_id, "closing_keyword")

    def test_hardening_preflight_slice_passes(self):
        failures = run_preflight_gate_checks(
            body="Closes #1456\n",
            labels=["Hardening", "area:tests"],
            base="release",
            changed_paths=[".agentic/releases/unreleased/hardening-1456.json"],
            owner="akasper",
            repo="plate",
            release_branch_mode="legacy",
            release_track_branches={"release": True},
        )
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
