"""Tests for release publisher gate helpers (#1488 / PR #1523)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from plate_core.release_publish_gate import (
    MISSING_RUN_ERROR,
    filter_workflow_runs_for_release,
    list_workflow_runs_for_publisher,
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

    @patch("plate_core.release_publish_gate._gh_api_paginated")
    def test_list_workflow_runs_paginates_head_sha_and_branch(self, mock_api):
        def side_effect(endpoint: str):
            if "head_sha=" in endpoint:
                return [
                    {
                        "id": 100,
                        "head_branch": "v0.13.0",
                        "head_sha": "deadbeef",
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": "2026-01-02T10:00:00Z",
                        "path": ".github/workflows/publish-pypi.yml",
                    }
                ]
            if "branch=" in endpoint:
                return [
                    {
                        "id": 101,
                        "head_branch": "v0.13.0",
                        "head_sha": "deadbeef",
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": "2026-01-03T10:00:00Z",
                        "path": ".github/workflows/publish-pypi.yml",
                    },
                    {
                        "id": 50,
                        "head_branch": "v0.13.0",
                        "head_sha": "other",
                        "status": "completed",
                        "conclusion": "failure",
                        "created_at": "2026-01-04T10:00:00Z",
                        "path": ".github/workflows/other.yml",
                    },
                ]
            raise AssertionError(endpoint)

        mock_api.side_effect = side_effect
        runs = list_workflow_runs_for_publisher(
            "akasper/plate",
            "publish-pypi.yml",
            release_tag="v0.13.0",
            head_sha="deadbeef",
        )
        self.assertEqual(mock_api.call_count, 2)
        self.assertEqual({int(r["databaseId"]) for r in runs}, {100, 101})

    @patch("plate_core.release_publish_gate.list_workflow_runs_for_publisher")
    def test_wait_fails_on_newest_completed_failure(self, mock_list):
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

    @patch("plate_core.release_publish_gate._gh_fetch_run")
    @patch("plate_core.release_publish_gate._gh_run_watch")
    @patch("plate_core.release_publish_gate.list_workflow_runs_for_publisher")
    def test_wait_watches_in_progress_then_judges_refreshed_conclusion(
        self, mock_list, mock_watch, mock_fetch
    ):
        mock_list.return_value = [
            {
                "databaseId": 42,
                "headBranch": "v0.13.0",
                "headSha": "deadbeef",
                "status": "in_progress",
                "conclusion": None,
                "createdAt": "2026-01-02T10:00:00Z",
            }
        ]
        mock_watch.return_value = 0
        mock_fetch.return_value = {
            "databaseId": 42,
            "headBranch": "v0.13.0",
            "headSha": "deadbeef",
            "status": "completed",
            "conclusion": "success",
            "createdAt": "2026-01-02T10:00:00Z",
        }
        result = wait_for_publisher_workflow(
            "akasper/plate",
            "publish-pypi.yml",
            release_tag="v0.13.0",
            head_sha="deadbeef",
            poll_attempts=1,
            poll_seconds=0,
        )
        self.assertTrue(result["ok"])
        mock_watch.assert_called_once_with("akasper/plate", 42)
        mock_fetch.assert_called_once_with("akasper/plate", 42)

    @patch("plate_core.release_publish_gate.list_workflow_runs_for_publisher")
    def test_wait_missing_run_fail_closed_with_clear_message(self, mock_list):
        mock_list.return_value = []
        result = wait_for_publisher_workflow(
            "akasper/plate",
            "publish-pypi.yml",
            release_tag="v0.13.0",
            head_sha="deadbeef",
            poll_attempts=2,
            poll_seconds=0,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("error"), MISSING_RUN_ERROR)
        self.assertIn("publish-pypi.yml", result.get("message", ""))
        self.assertIn("v0.13.0", result.get("message", ""))
        self.assertIn("deadbeef", result.get("message", ""))


if __name__ == "__main__":
    unittest.main()