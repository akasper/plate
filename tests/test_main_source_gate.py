"""Tests for main-source PR gate (#1435)."""

from __future__ import annotations

import unittest

from plate_core.pr_gates_checks import (
    MAIN_SOURCE_OVERRIDE_LABEL,
    check_main_source,
    is_allowed_main_source_head,
    run_preflight_gate_checks,
)
from plate_core.pr_main_source_gate import run_gate
from plate_core.pr_preflight import run_preflight


class MainSourceGateTests(unittest.TestCase):
    def test_allowed_release_heads(self):
        for head in (
            "release",
            "release-patch",
            "release-minor",
            "release-major",
            "release-v1.2.3",
        ):
            with self.subTest(head=head):
                self.assertTrue(is_allowed_main_source_head(head))
                self.assertIsNone(check_main_source("main", head, ["Feature"]))

    def test_feature_branch_into_main_fails(self):
        failure = check_main_source("main", "cursor/feature-foo", ["Feature"])
        self.assertIsNotNone(failure)
        self.assertEqual(failure.check_id, "main_source")

    def test_override_label_passes(self):
        self.assertIsNone(
            check_main_source(
                "main",
                "cursor/feature-foo",
                ["Feature", MAIN_SOURCE_OVERRIDE_LABEL],
            )
        )

    def test_non_main_base_unaffected(self):
        self.assertIsNone(
            check_main_source("release", "cursor/feature-foo", ["Feature"])
        )

    def test_cli_gate_exit_code(self):
        self.assertEqual(run_gate(base="main", head="release", labels=["Release"]), 0)
        self.assertEqual(
            run_gate(base="main", head="cursor/x", labels=["Feature"]),
            1,
        )

    def test_preflight_reports_main_source_failure(self):
        report = run_preflight(
            body="Closes #1435",
            labels=["Feature", "area:infra"],
            base="main",
            head="cursor/main-source-check-1435",
            changed_paths=[".agentic/releases/unreleased/main-source-1435.json"],
            repo="akasper/plate",
            release_status={
                "release_branch_mode": "legacy",
                "release_track_branches": {"release": True},
            },
        )
        self.assertFalse(report["passed"])
        ids = [item["id"] for item in report["failures"]]
        self.assertIn("main_source", ids)

    def test_preflight_gate_list_includes_main_source(self):
        failures = run_preflight_gate_checks(
            body="Closes #1",
            labels=["Feature", "area:infra"],
            base="main",
            head="feature/x",
            changed_paths=[".agentic/releases/unreleased/x.json"],
            owner="o",
            repo="r",
            release_branch_mode="legacy",
            release_track_branches={"release": True},
        )
        self.assertTrue(any(f.check_id == "main_source" for f in failures))


if __name__ == "__main__":
    unittest.main()
