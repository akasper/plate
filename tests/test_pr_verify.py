"""Tests for gh plate pr verify / plate_pr_verify (#1365)."""

from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from plate_core.branch_policy_inputs import BranchPolicyContext
from plate_core.release import ReleaseStatusReport
from plate_core.pr_verify import (
    _fetch_commit_statuses,
    _fetch_compare_behind,
    _load_review_threads_paginated,
    effective_ci_snapshot,
    format_pr_verify_text,
    latest_check_run_by_name,
    latest_status_by_context,
    run_unittest_discover,
    verify_pr,
)


class _FakeClient:
    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple] = []

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
        self.calls.append((endpoint, method, fields))
        if endpoint == "graphql" and method == "POST" and fields:
            query = fields.get("query") or ""
            if "pageInfo" in query and "reviewThreads" in query:
                return self.responses.get(
                    ("graphql", "threads"),
                    self.responses.get(("graphql", "load"), self.responses.get("graphql", {})),
                )
            if "pullRequest" in query:
                return self.responses.get(("graphql", "load"), self.responses.get("graphql", {}))
        key = (endpoint, method)
        if fields and method == "GET":
            key = (endpoint, method, tuple(sorted((fields or {}).items())))
        return self.responses.get(key, self.responses.get(endpoint, {}))


def _verify_pr_fixtures(overrides=None):
    base = {
        "repos/o/r/pulls/9": _good_pull(),
        "repos/o/r/pulls/9/files": [{"filename": ".agentic/releases/unreleased/pr-verify-1365.json"}],
        "repos/o/r/compare/base111...abc123": {"behind_by": 0, "ahead_by": 1},
        "repos/o/r/commits/abc123/status": {"state": "success", "total_count": 0, "statuses": []},
        ("repos/o/r/commits/abc123/statuses", "GET", (("page", 1), ("per_page", 100))): [],
        "repos/o/r/commits/abc123/check-runs": {
            "check_runs": [
                {"name": "labels", "status": "completed", "conclusion": "success", "id": 1},
                {"name": "test", "status": "completed", "conclusion": "success", "id": 2},
                {"name": "pr-gates", "status": "completed", "conclusion": "success", "id": 3},
            ]
        },
        ("graphql", "load"): {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "CLEAN",
                        "baseRefName": "main",
                        "headRefName": "feature/x",
                        "reviewDecision": None,
                        "statusCheckRollup": {"state": "SUCCESS"},
                        "reviewThreads": {"nodes": []},
                    }
                }
            }
        },
        ("graphql", "threads"): {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [],
                        }
                    }
                }
            }
        },
    }
    if overrides:
        base.update(overrides)
    return base


@contextmanager
def _verify_pr_context(*, issue_labels: list[str] | None = None):
    ctx = BranchPolicyContext(
        release_status=_release_status_legacy(),
        issue_labels=issue_labels or [],
    )
    with patch("plate_core.pr_verify.fetch_required_check_contexts", return_value=frozenset()):
        with patch("plate_core.pr_verify.gather_branch_policy_context", return_value=(ctx, None)):
            yield


def _release_status_legacy() -> ReleaseStatusReport:
    return ReleaseStatusReport(
        repo="o/r",
        release_branch_exists=True,
        release_track_branches={
            "release": True,
            "release-major": False,
            "release-minor": False,
            "release-patch": False,
        },
        release_branch_mode="legacy",
        release_branch_reset_target="main",
        warnings=[],
        open_release_issues=[],
        current_version=None,
        latest_version=None,
        pending_fragment_count=0,
        pending_fragments=[],
        extension_release_checks=[],
    )


def _good_pull(**overrides):
    base = {
        "body": "Summary\n\nCloses #1365\n",
        "labels": [{"name": "Feature"}, {"name": "area:agent"}],
        "base": {"ref": "release", "sha": "base111"},
        "head": {"ref": "feature/x", "sha": "abc123"},
        "milestone": {"title": "Agent crews"},
    }
    base.update(overrides)
    return base


class TestCheckRunDedupe(unittest.TestCase):
    def test_cancelled_superseded_by_later_success(self):
        runs = [
            {"name": "test", "status": "completed", "conclusion": "cancelled", "id": 1, "started_at": "2026-01-01T00:00:00Z"},
            {"name": "test", "status": "completed", "conclusion": "success", "id": 2, "started_at": "2026-01-02T00:00:00Z"},
        ]
        latest = latest_check_run_by_name(runs)
        snap = effective_ci_snapshot({}, list(latest.values()), required=frozenset(["test"]))
        self.assertEqual(snap["failing"], [])
        self.assertEqual(snap["pending"], [])

    def test_queued_rerun_without_timestamps_is_pending(self):
        runs = [
            {
                "name": "test",
                "status": "completed",
                "conclusion": "success",
                "id": 10,
                "started_at": "2026-01-01T00:00:00Z",
            },
            {"name": "test", "status": "queued", "conclusion": None, "id": 99},
        ]
        latest = latest_check_run_by_name(runs)
        snap = effective_ci_snapshot({}, list(latest.values()), required=frozenset(["test"]))
        self.assertEqual(snap["pending"], ["test"])
        self.assertEqual(snap["failing"], [])

    def test_mixed_case_required_context_evaluates_failure(self):
        runs = [{"name": "test", "status": "completed", "conclusion": "failure", "id": 1}]
        snap = effective_ci_snapshot({}, runs, required=frozenset(["Test"]))
        self.assertIn("Test", snap["failing"])

    def test_stale_conclusion_fails_required_check(self):
        runs = [{"name": "ci", "status": "completed", "conclusion": "stale", "id": 1}]
        snap = effective_ci_snapshot({}, runs, required=frozenset(["ci"]))
        self.assertIn("ci", snap["failing"])

    def test_check_run_and_status_both_must_pass(self):
        runs = [{"name": "gate", "status": "completed", "conclusion": "success", "id": 1}]
        status = {
            "statuses": [
                {"context": "gate", "state": "failure", "updated_at": "2026-01-02T00:00:00Z"}
            ]
        }
        snap = effective_ci_snapshot(status, runs, required=frozenset(["gate"]))
        self.assertIn("gate", snap["failing"])

    def test_paginated_status_context_beyond_first_page(self):
        page1 = [{"context": f"ctx{i}", "state": "success", "updated_at": "2026-01-01T00:00:00Z"} for i in range(30)]
        page2 = [
            {"context": "legacy-required", "state": "success", "updated_at": "2026-01-02T00:00:00Z"}
        ]
        status_json = {"state": "success", "statuses": page1 + page2}
        snap = effective_ci_snapshot(status_json, [], required=frozenset(["legacy-required"]))
        self.assertEqual(snap["missing_required"], [])
        self.assertEqual(snap["failing"], [])
        latest = latest_status_by_context(status_json)
        self.assertIn("legacy-required", latest)


class TestStatusPagination(unittest.TestCase):
    def test_fetch_commit_statuses_merges_all_pages(self):
        client = _FakeClient(
            {
                "repos/o/r/commits/sha/status": {"state": "success", "statuses": []},
                ("repos/o/r/commits/sha/statuses", "GET", (("page", 1), ("per_page", 100))): [
                    {"context": f"c{i}", "state": "success", "updated_at": "2026-01-01T00:00:00Z"}
                    for i in range(100)
                ],
                ("repos/o/r/commits/sha/statuses", "GET", (("page", 2), ("per_page", 100))): [
                    {
                        "context": "legacy-required",
                        "state": "success",
                        "updated_at": "2026-01-02T00:00:00Z",
                    }
                ],
            }
        )
        payload = _fetch_commit_statuses(client, "o/r", "sha")
        contexts = [item["context"] for item in payload.get("statuses") or []]
        self.assertIn("legacy-required", contexts)
        self.assertEqual(len(contexts), 101)


class TestVerifyPr(unittest.TestCase):
    def test_happy_path_feature_pr(self):
        client = _FakeClient(_verify_pr_fixtures())
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        self.assertTrue(report["passed"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("base_branch", ids)
        self.assertIn("release_fragment", ids)
        self.assertIn("review_threads", ids)

    def test_epic_fragment_directory_accepted(self):
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    "repos/o/r/pulls/9/files": [
                        {"filename": ".agentic/releases/epic-123-delete-boondoggles/change.json"}
                    ],
                }
            )
        )
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        fragment = next(c for c in report["checks"] if c["id"] == "release_fragment")
        self.assertTrue(fragment["passed"])

    def test_removed_fragment_file_does_not_count(self):
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    "repos/o/r/pulls/9/files": [
                        {
                            "filename": ".agentic/releases/unreleased/old.json",
                            "status": "removed",
                        }
                    ],
                }
            )
        )
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        fragment = next(c for c in report["checks"] if c["id"] == "release_fragment")
        self.assertFalse(fragment["passed"])

    def test_base_sync_fails_when_behind_by_positive(self):
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    "repos/o/r/compare/base111...abc123": {"behind_by": 2, "ahead_by": 1},
                    ("graphql", "load"): {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "mergeStateStatus": "CLEAN",
                                    "baseRefName": "main",
                                    "headRefName": "feature/x",
                                    "reviewThreads": {"nodes": []},
                                }
                            }
                        }
                    },
                }
            )
        )
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        sync = next(c for c in report["checks"] if c["id"] == "base_sync")
        self.assertFalse(sync["passed"])

    def test_review_thread_pagination_incomplete_fails_closed(self):
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    ("graphql", "threads"): {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "pageInfo": {"hasNextPage": True, "endCursor": "abc"},
                                        "nodes": [{"id": "T0", "isResolved": True, "comments": {"nodes": []}}],
                                    }
                                }
                            }
                        }
                    },
                }
            )
        )
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        threads = next(c for c in report["checks"] if c["id"] == "review_threads")
        self.assertFalse(threads["passed"])

    def test_fails_on_wrong_integration_base(self):
        multi_status = ReleaseStatusReport(
            repo="o/r",
            release_branch_exists=False,
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
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    "repos/o/r/pulls/9": _good_pull(base={"ref": "release-patch", "sha": "base111"}),
                    "repos/o/r/pulls/9/files": [],
                }
            )
        )
        ctx = BranchPolicyContext(release_status=multi_status, issue_labels=[])
        with patch("plate_core.pr_verify.fetch_required_check_contexts", return_value=frozenset()):
            with patch("plate_core.pr_verify.gather_branch_policy_context", return_value=(ctx, None)):
                report = verify_pr(9, repo="o/r", client=client)
        base_check = next(c for c in report["checks"] if c["id"] == "base_branch")
        self.assertFalse(base_check["passed"])

    def test_unresolved_threads_fail(self):
        client = _FakeClient(
            _verify_pr_fixtures(
                {
                    ("graphql", "threads"): {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {
                                                "id": "T1",
                                                "isResolved": False,
                                                "isOutdated": False,
                                                "path": "a.py",
                                                "comments": {
                                                    "nodes": [{"author": {"login": "bot"}, "body": "x"}]
                                                },
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    },
                }
            )
        )
        with _verify_pr_context():
            report = verify_pr(9, repo="o/r", client=client)
        self.assertFalse(report["passed"])
        thread_check = next(c for c in report["checks"] if c["id"] == "review_threads")
        self.assertFalse(thread_check["passed"])

    def test_format_text_and_json_serializable(self):
        report = {
            "repo": "o/r",
            "pr_number": 1,
            "passed": False,
            "checks": [{"id": "base_branch", "passed": False, "message": "bad base"}],
        }
        text = format_pr_verify_text(report)
        self.assertIn("FAIL", text)
        json.dumps(report)


class TestCompareAndThreads(unittest.TestCase):
    def test_compare_behind_unverified_without_shas(self):
        client = _FakeClient({})
        result = _fetch_compare_behind(client, "o/r", "", "abc")
        self.assertFalse(result["verified"])

    def test_load_review_threads_paginates(self):
        calls: list[str | None] = []

        class _PagingClient(_FakeClient):
            def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
                if endpoint == "graphql" and method == "POST":
                    calls.append((fields or {}).get("after"))
                    if calls[-1] is None:
                        return {
                            "data": {
                                "repository": {
                                    "pullRequest": {
                                        "reviewThreads": {
                                            "pageInfo": {"hasNextPage": True, "endCursor": "CUR1"},
                                            "nodes": [{"id": "A", "isResolved": True, "comments": {"nodes": []}}],
                                        }
                                    }
                                }
                            }
                        }
                    return {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                        "nodes": [
                                            {
                                                "id": "B",
                                                "isResolved": False,
                                                "comments": {"nodes": [{"author": {"login": "x"}}]},
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    }
                return super().api(endpoint, method, fields)

        nodes, complete = _load_review_threads_paginated(_PagingClient({}), "o/r", 1)
        self.assertTrue(complete)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(calls, [None, "CUR1"])


class TestRunUnittestDiscover(unittest.TestCase):
    def test_parses_count_and_stale_warning(self):
        class _Result:
            returncode = 0
            stdout = "Ran 1210 tests in 10s\nOK"
            stderr = ""

        report = run_unittest_discover(runner=lambda *a, **k: _Result())
        self.assertEqual(report["test_count"], 1210)
        self.assertTrue(report["stale_base_warning"])

    @patch("plate_core.pr_verify.run_hidden")
    def test_default_runner_is_run_hidden(self, mock_run_hidden):
        class _Result:
            returncode = 0
            stdout = "Ran 1400 tests in 10s\nOK"
            stderr = ""

        mock_run_hidden.return_value = _Result()
        report = run_unittest_discover()
        mock_run_hidden.assert_called_once()
        self.assertEqual(report["test_count"], 1400)


class TestMcpPlatePrVerify(unittest.TestCase):
    @patch("plate_core.mcp_server._write")
    @patch("plate_core.mcp_server.verify_pr")
    def test_tools_call_plate_pr_verify(self, mock_verify, mock_write):
        from plate_core.mcp_server import _handle_tools_call

        mock_verify.return_value = {"repo": "o/r", "pr_number": 5, "passed": True, "checks": []}
        _handle_tools_call(99, {"name": "plate_pr_verify", "arguments": {"repo": "o/r", "pr_number": 5}})
        mock_verify.assert_called_once()
        payload = json.loads(mock_write.call_args[0][0]["result"]["content"][0]["text"])
        self.assertTrue(payload["passed"])


if __name__ == "__main__":
    unittest.main()
