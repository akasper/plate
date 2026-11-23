"""Tests for release-window PR gate (#1439)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from plate_core.pr_gates_checks import (
    RELEASE_WINDOW_OVERRIDE_LABEL,
    check_release_window,
    run_preflight_gate_checks,
)
from plate_core.pr_release_window_gate import run_gate


class ReleaseWindowGateTests(unittest.TestCase):
    def test_blocks_release_base_when_window_open(self):
        failure = check_release_window(
            "release-minor",
            ["Feature", "area:infra"],
            release_window_open=True,
        )
        self.assertIsNotNone(failure)
        self.assertEqual(failure.check_id, "release_window")

    def test_override_passes(self):
        self.assertIsNone(
            check_release_window(
                "release",
                ["Feature", RELEASE_WINDOW_OVERRIDE_LABEL],
                release_window_open=True,
            )
        )

    def test_closed_window_passes(self):
        self.assertIsNone(
            check_release_window(
                "release-major",
                ["Feature"],
                release_window_open=False,
            )
        )

    def test_main_base_unaffected(self):
        self.assertIsNone(
            check_release_window("main", ["Feature"], release_window_open=True)
        )

    @patch("plate_core.pr_release_window_gate.get_release_status")
    def test_cli_gate_exit_code(self, mock_status: MagicMock) -> None:
        mock_status.return_value = MagicMock(release_window_open=True)
        self.assertEqual(run_gate(base="release", labels=["Feature"], repo="o/r"), 1)
        mock_status.return_value = MagicMock(release_window_open=False)
        self.assertEqual(run_gate(base="release", labels=["Feature"], repo="o/r"), 0)

    def test_preflight_gate_list_includes_release_window(self):
        failures = run_preflight_gate_checks(
            body="Closes #1",
            labels=["Feature", "area:infra"],
            base="release-minor",
            head="feature/x",
            changed_paths=[".agentic/releases/unreleased/x.json"],
            owner="o",
            repo="r",
            release_branch_mode="multi-track",
            release_track_branches={"release-minor": True},
            release_window_open=True,
        )
        self.assertTrue(any(f.check_id == "release_window" for f in failures))


if __name__ == "__main__":
    unittest.main()
