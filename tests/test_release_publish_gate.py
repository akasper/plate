"""Tests for release publisher gate helpers (#1488 / PR #1523)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.release_publish_gate import (
    filter_workflow_runs_for_release,
    pick_publisher_workflow_run,
    publisher_run_succeeded,
    should_verify_publishers_for_tag,
    wait_for_publisher_workflow,
)


class ReleasePublishGateTests(unittest.TestCase):
    def test_should_verify_publishers_when_tag_at_merge_sha(self):
        self.assertTrue(should_verify_publishers_for_tag(tag_at_merge_sha=True))
        self.assertFalse(should_verify_publishers_for_tag(tag_at_merge_sha=False))

    def test_filter_runs_by_tag_or_head_sha(self):
        runs = [
            {"headBranch": "main", "headSha": "aaa", "createdAt": "2026-01-01T00:00:00Z"},
            {"headBranch": "v0.13.0", "headSha": "bbb", "createdAt": "2026-01-02T00:00:00Z"},
            {"headBranch": "feature", "headSha": "ccc", "createdAt": "2026-01-03T00:00:00Z"},
        ]
        matched = filter_workflow_runs_for_release(
            runs, release_tag="v0.13.0", head_sha="ccc"
        )
        self.assertEqual(len(matched), 2)
        self.assertEqual({r["headBranch"] for r in matched}, {"v0.13.0", "feature"})

    def test_pick_newest_by_created_not_arbitrary_index_zero(self):
        runs = [
            {
                "databaseId": 1,
                "headBranch": "v0.13.0",
                "headSha": "old",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-01-01T10:00:00Z",
            },
            {
                "databaseId": 2,
                "headBranch": "v0.13.0",
                "headSha": "new",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-01-02T10:00:00Z",
            },
            {
                "databaseId": 3,
                "headBranch": "main",
                "headSha": "noise",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-01-03T10:00:00Z",
            },
        ]
        picked = pick_publisher_workflow_run(runs, release_tag="v0.13.0", head_sha="new")
        self.assertEqual(picked["databaseId"], 2)
        self.assertTrue(publisher_run_succeeded(picked))

    @patch("plate_core.release_publish_gate._gh_run_watch")
    @patch("plate_core.release_publish_gate._gh_run_list")
    def test_wait_fails_on_newest_completed_failure(self, mock_list, mock_watch):
        mock_list.return_value = [
            {
                "databaseId": 9,
                "headBranch": "v0.13.0",
                "headSha": "deadbeef",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-01-02T10:00:00Z",
            },
            {
                "databaseId": 8,
                "headBranch": "v0.13.0",
                "headSha": "deadbeef",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-01-01T10:00:00Z",
            },
        ]
        result = wait_for_publisher_workflow(
            "akasper/plate",
            "publish-pypi.yml",
            release_tag="v0.13.0",
            head_sha="deadbeef",
            poll_attempts=1,
            poll_seconds=0,
        )
        self.assertFalse(result["ok"])
        mock_watch.assert_not_called()


if __name__ == "__main__":
    unittest.main()