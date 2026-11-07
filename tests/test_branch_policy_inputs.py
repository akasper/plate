"""Tests for branch policy shared inputs (#1449)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.branch_policy_inputs import (
    fetch_labels_for_linked_issues,
    gather_branch_policy_context,
)
from plate_core.github_client import GhApiError
from plate_core.release import ReleaseStatusReport


def _status(**overrides) -> ReleaseStatusReport:
    base = ReleaseStatusReport(
        repo="o/r",
        release_branch_exists=True,
        release_track_branches={
            "release": False,
            "release-major": True,
            "release-minor": True,
            "release-patch": True,
        },
        release_branch_mode="multi-track",
        release_branch_reset_target="main",
        warnings=[],
        open_release_issues=[],
        current_version=None,
        latest_version=None,
        pending_fragment_count=0,
        pending_fragments=[],
        extension_release_checks=[],
    )
    for key, val in overrides.items():
        setattr(base, key, val)
    return base


class BranchPolicyInputsTests(unittest.TestCase):
    def test_fetch_issue_labels_merges_major(self):
        class _Gh:
            def api(self, endpoint: str):
                if endpoint.endswith("/issues/42"):
                    return {"labels": [{"name": "Major"}, {"name": "Feature"}]}
                raise AssertionError(endpoint)

        labels, err = fetch_labels_for_linked_issues("o/r", [42], client=_Gh())  # type: ignore[arg-type]
        self.assertIsNone(err)
        self.assertIn("Major", labels)

    def test_fetch_issue_labels_fail_closed_on_api_error(self):
        class _Gh:
            def api(self, _endpoint: str):
                raise GhApiError("rate limit")

        labels, err = fetch_labels_for_linked_issues("o/r", [1], client=_Gh())  # type: ignore[arg-type]
        self.assertEqual(labels, [])
        self.assertIn("rate limit", err or "")

    def test_gather_fails_on_unverified_branches(self):
        status = _status(
            release_branch_mode="unverified",
            branch_verification_errors=["release-minor: HTTP 503"],
        )
        with patch("plate_core.branch_policy_inputs.get_release_status", return_value=status):
            ctx, fail = gather_branch_policy_context(
                repo="o/r",
                pr_labels=["Feature"],
                body="Closes #1\n",
            )
        self.assertIsNone(ctx)
        self.assertIsNotNone(fail)


if __name__ == "__main__":
    unittest.main()
