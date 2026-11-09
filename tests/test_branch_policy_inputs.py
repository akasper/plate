"""Tests for branch policy shared inputs (#1449)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.branch_policy_inputs import gather_branch_policy_context
from plate_core.issue_context import IssueContextResult, IssueContextStatus
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
    def test_gather_includes_issue_labels_when_resolved(self):
        status = _status()
        with patch(
            "plate_core.branch_policy_inputs.resolve_issue_context",
            return_value=IssueContextResult(
                status=IssueContextStatus.OK,
                labels=["Minor", "Feature"],
            ),
        ):
            ctx, fail = gather_branch_policy_context(
                repo="o/r",
                pr_labels=["Feature"],
                body="Closes #1\n",
                release_status=status,
                pr_number=99,
            )
        self.assertIsNone(fail)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertIn("Minor", ctx.issue_labels)

    def test_gather_fails_on_issue_unavailable(self):
        status = _status()
        with patch(
            "plate_core.branch_policy_inputs.resolve_issue_context",
            return_value=IssueContextResult(
                status=IssueContextStatus.UNAVAILABLE,
                message="sidebar API down",
            ),
        ):
            ctx, fail = gather_branch_policy_context(
                repo="o/r",
                pr_labels=["Feature"],
                body="Closes #1\n",
                release_status=status,
            )
        self.assertIsNone(ctx)
        self.assertIsNotNone(fail)
        assert fail is not None
        self.assertIn("sidebar", fail.message)

    def test_gather_fails_on_unverified_branches(self):
        status = _status(
            release_branch_mode="unverified",
            branch_verification_errors=["release-minor: HTTP 503"],
        )
        ctx, fail = gather_branch_policy_context(
            repo="o/r",
            pr_labels=["Feature"],
            body="Summary only\n",
            release_status=status,
        )
        self.assertIsNone(ctx)
        self.assertIsNotNone(fail)


if __name__ == "__main__":
    unittest.main()
