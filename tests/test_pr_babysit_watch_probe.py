"""Tests for cheap probe-wired gh plate pr babysit --watch loop (#1077)."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from plate_core.cli import main
from plate_core.pr_babysit import BabysitReport
from plate_core.pr_watch_probe import ProbeResult, ProbeState, save_probe_state


def _open_pr_body() -> dict:
    return {"state": "open", "merged": False}


def _probe_200(state: ProbeState | None = None, *, changed: bool = True) -> ProbeResult:
    base = state or ProbeState()
    return ProbeResult(
        changed=changed,
        not_modified=False,
        pr=_open_pr_body(),
        new_state=ProbeState(
            etag='W/"etag"',
            head_sha="abc",
            updated_at="2026-01-01T00:00:00Z",
            mergeable_state="clean",
            ci_state="success",
            last_checked_at="2026-01-01T00:00:01Z",
            last_issue_comment_id=base.last_issue_comment_id,
            last_review_comment_id=base.last_review_comment_id,
            last_review_id=base.last_review_id,
        ),
    )


def _probe_304(state: ProbeState) -> ProbeResult:
    return ProbeResult(
        changed=False,
        not_modified=True,
        pr=None,
        new_state=state,
    )


def _probe_304_ci_changed(state: ProbeState) -> ProbeResult:
    return ProbeResult(
        changed=True,
        not_modified=True,
        pr=None,
        new_state=ProbeState(
            etag=state.etag,
            head_sha=state.head_sha,
            updated_at=state.updated_at,
            mergeable_state=state.mergeable_state,
            ci_state="success",
            last_checked_at="2026-01-01T00:00:02Z",
            last_issue_comment_id=state.last_issue_comment_id,
            last_review_comment_id=state.last_review_comment_id,
            last_review_id=state.last_review_id,
        ),
    )


class BabysitWatchProbeWiringTests(unittest.TestCase):
    def _run_watch(
        self,
        directory: str,
        probe_side_effect,
        *,
        argv: list[str] | None = None,
        fetch_delta_side_effect=None,
        pid_alive=None,
    ):
        argv = argv or ["pr", "babysit", "99", "--watch", "--repo", "owner/repo"]
        ledger_path = Path(directory) / "watch.caps.json"
        probe_path = Path(directory) / "probe.json"
        claim = {
            "claimed": True,
            "pidfile": str(Path(directory) / "watch.pid"),
            "pid": 11,
            "ppid": 22,
        }
        if pid_alive is None:
            pid_alive = [True, True, True, True, False]

        babysit_report = BabysitReport("owner/repo", 99, 0, 0, False)
        patches = {
            "resolve_repo": patch("plate_core.cli.resolve_repo", return_value="owner/repo"),
            "caps_path": patch("plate_core.cli.caps_path", return_value=ledger_path),
            "probe_state_path": patch("plate_core.cli.probe_state_path", return_value=probe_path),
            "claim": patch("plate_core.cli.claim_babysit_watch", return_value=claim),
            "pid": patch("plate_core.cli.pid_is_alive", side_effect=pid_alive),
            "probe": patch("plate_core.cli.probe_pr", side_effect=probe_side_effect),
            "babysit": patch("plate_core.cli.babysit_pr", return_value=babysit_report),
            "sleep": patch("plate_core.cli.sleep_until_watch_interval", return_value=True),
            "clear": patch("plate_core.cli.clear_babysit_watch_pid"),
            "record_wake": patch("plate_core.cli.record_wake"),
        }
        if fetch_delta_side_effect is not None:
            patches["fetch_delta"] = patch(
                "plate_core.cli.fetch_delta", side_effect=fetch_delta_side_effect
            )
        else:
            patches["fetch_delta"] = patch("plate_core.cli.fetch_delta")

        started: dict = {}
        with ExitStack() as stack:
            for key, ctx in patches.items():
                started[key] = stack.enter_context(ctx)
            code = main(argv)
        return code, started

    def test_three_quiet_304_ticks_backoff_and_single_baseline_babysit(self):
        saved = ProbeState(etag='W/"etag"', head_sha="abc")
        with tempfile.TemporaryDirectory() as directory:
            _, mocks = self._run_watch(
                directory,
                [_probe_200(), _probe_304(saved), _probe_304(saved), _probe_304(saved)],
            )

        self.assertEqual(mocks["babysit"].call_count, 1)
        self.assertEqual(mocks["record_wake"].call_count, 1)
        self.assertEqual(
            [call.args[0] for call in mocks["sleep"].call_args_list],
            [60, 60, 120, 240],
        )
        mocks["fetch_delta"].assert_not_called()

    def test_actionable_copilot_review_comment_runs_babysit_and_resets_backoff(self):
        prev = ProbeState(
            etag='W/"etag"',
            head_sha="old",
            updated_at="2026-01-01T00:00:00Z",
            mergeable_state="clean",
            ci_state="success",
            last_checked_at="2026-01-01T00:00:00Z",
        )
        changed = _probe_200(prev, changed=True)
        changed.new_state.head_sha = "new"
        delta_state = ProbeState(
            etag='W/"etag"',
            head_sha="new",
            updated_at="2026-01-02T00:00:00Z",
            mergeable_state="clean",
            ci_state="success",
            last_checked_at="2026-01-02T00:00:00Z",
            last_review_comment_id=42,
        )
        delta = {
            "issue_comments": [],
            "review_comments": [
                {
                    "id": 42,
                    "user": {"login": "Copilot"},
                    "body": "Consider this fix",
                    "path": "src/a.py",
                    "line": 10,
                    "html_url": "https://github.com/owner/repo/pull/99#discussion_r42",
                }
            ],
            "reviews": [],
            "new_state": delta_state,
        }

        with tempfile.TemporaryDirectory() as directory:
            probe_path = Path(directory) / "probe.json"
            save_probe_state(probe_path, prev)
            _, mocks = self._run_watch(
                directory,
                [changed],
                fetch_delta_side_effect=[delta],
                pid_alive=[True, False],
            )

        self.assertEqual(mocks["babysit"].call_count, 1)
        mocks["record_wake"].assert_called_once()
        self.assertEqual(mocks["sleep"].call_args_list[0].args[0], 60)

    def test_bot_only_issue_comment_is_not_actionable(self):
        prev = ProbeState(
            etag='W/"etag"',
            head_sha="abc",
            updated_at="2026-01-01T00:00:00Z",
            mergeable_state="clean",
            ci_state="success",
        )
        changed = _probe_200(prev, changed=True)
        changed.new_state.updated_at = "2026-01-01T01:00:00Z"
        delta_state = ProbeState(
            etag='W/"etag"',
            head_sha="abc",
            updated_at="2026-01-01T01:00:00Z",
            mergeable_state="clean",
            ci_state="success",
            last_issue_comment_id=7,
        )
        delta = {
            "issue_comments": [
                {
                    "id": 7,
                    "user": {"login": "dependabot[bot]"},
                    "body": "Bumps lodash",
                    "html_url": "https://github.com/owner/repo/issues/99#issuecomment-7",
                }
            ],
            "review_comments": [],
            "reviews": [],
            "new_state": delta_state,
        }

        with tempfile.TemporaryDirectory() as directory:
            probe_path = Path(directory) / "probe.json"
            save_probe_state(probe_path, prev)
            _, mocks = self._run_watch(
                directory,
                [changed],
                fetch_delta_side_effect=[delta],
                pid_alive=[True, False],
            )

        mocks["babysit"].assert_not_called()
        mocks["record_wake"].assert_not_called()

    def test_merged_pr_stops_watch(self):
        merged = ProbeResult(
            changed=True,
            not_modified=False,
            pr={"state": "closed", "merged": True, "merged_at": "2026-01-03T00:00:00Z"},
            new_state=ProbeState(),
        )
        with tempfile.TemporaryDirectory() as directory:
            _, mocks = self._run_watch(
                directory,
                [merged],
                pid_alive=[True, False],
            )

        mocks["babysit"].assert_not_called()
        mocks["sleep"].assert_not_called()

    def test_304_with_ci_change_runs_babysit_and_records_wake(self):
        prev = ProbeState(
            etag='W/"etag"',
            head_sha="abc",
            updated_at="2026-01-01T00:00:00Z",
            mergeable_state="clean",
            ci_state="pending",
            last_checked_at="2026-01-01T00:00:00Z",
        )
        probe = _probe_304_ci_changed(prev)
        delta_state = probe.new_state
        delta = {
            "issue_comments": [],
            "review_comments": [],
            "reviews": [],
            "new_state": delta_state,
        }

        with tempfile.TemporaryDirectory() as directory:
            probe_path = Path(directory) / "probe.json"
            save_probe_state(probe_path, prev)
            _, mocks = self._run_watch(
                directory,
                [probe],
                fetch_delta_side_effect=[delta],
                pid_alive=[True, False],
            )

        mocks["fetch_delta"].assert_called_once()
        mocks["babysit"].assert_called_once()
        mocks["record_wake"].assert_called_once()

    def test_full_every_forces_periodic_babysit(self):
        saved = ProbeState(etag='W/"etag"', head_sha="abc")
        with tempfile.TemporaryDirectory() as directory:
            _, mocks = self._run_watch(
                directory,
                [_probe_200(), _probe_304(saved)],
                argv=[
                    "pr",
                    "babysit",
                    "99",
                    "--watch",
                    "--repo",
                    "owner/repo",
                    "--full-every",
                    "2",
                ],
                pid_alive=[True, True, False],
            )

        self.assertEqual(mocks["babysit"].call_count, 2)
        self.assertEqual(mocks["record_wake"].call_count, 2)


if __name__ == "__main__":
    unittest.main()
