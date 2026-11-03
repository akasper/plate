"""Tests for gh plate pr verify / plate_pr_verify (#1365)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from plate_core.pr_verify import (
    effective_ci_snapshot,
    format_pr_verify_text,
    latest_check_run_by_name,
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
            if "pullRequest" in query:
                return self.responses.get(("graphql", "load"), self.responses.get("graphql", {}))
        key = (endpoint, method)
        if fields and method == "GET":
            key = (endpoint, method, tuple(sorted((fields or {}).items())))
        return self.responses.get(key, self.responses.get(endpoint, {}))


def _good_pull(**overrides):
    base = {
        "body": "Summary\n\nCloses #1365\n",
        "labels": [{"name": "Feature"}, {"name": "area:agent"}],
        "base": {"ref": "main"},
        "head": {"sha": "abc123"},
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


class TestVerifyPr(unittest.TestCase):
    def test_happy_path_feature_pr(self):
        client = _FakeClient(
            {
                "repos/o/r/pulls/9": _good_pull(),
                "repos/o/r/pulls/9/files": [{"filename": ".agentic/releases/unreleased/pr-verify-1365.json"}],
                "repos/o/r/commits/abc123/status": {"state": "success", "total_count": 0},
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
            }
        )
        with patch("plate_core.pr_verify.fetch_required_check_contexts", return_value=frozenset()):
            report = verify_pr(9, repo="o/r", client=client)
        self.assertTrue(report["passed"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("base_branch", ids)
        self.assertIn("release_fragment", ids)
        self.assertIn("review_threads", ids)

    def test_fails_on_release_base(self):
        client = _FakeClient(
            {
                "repos/o/r/pulls/9": _good_pull(base={"ref": "release"}),
                "repos/o/r/pulls/9/files": [],
                "repos/o/r/commits/abc123/status": {"state": "success", "total_count": 0},
                "repos/o/r/commits/abc123/check-runs": {"check_runs": []},
                ("graphql", "load"): {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "mergeStateStatus": "CLEAN",
                                "baseRefName": "release",
                                "headRefName": "feature/x",
                                "reviewThreads": {"nodes": []},
                            }
                        }
                    }
                },
            }
        )
        with patch("plate_core.pr_verify.fetch_required_check_contexts", return_value=frozenset()):
            report = verify_pr(9, repo="o/r", client=client)
        self.assertFalse(report["passed"])
        base_check = next(c for c in report["checks"] if c["id"] == "base_branch")
        self.assertFalse(base_check["passed"])

    def test_unresolved_threads_fail(self):
        client = _FakeClient(
            {
                "repos/o/r/pulls/9": _good_pull(),
                "repos/o/r/pulls/9/files": [{"filename": ".agentic/releases/unreleased/x.json"}],
                "repos/o/r/commits/abc123/status": {"state": "success", "total_count": 0},
                "repos/o/r/commits/abc123/check-runs": {
                    "check_runs": [
                        {"name": n, "status": "completed", "conclusion": "success", "id": i}
                        for i, n in enumerate(["labels", "test", "pr-gates"], start=1)
                    ]
                },
                ("graphql", "load"): {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "mergeStateStatus": "CLEAN",
                                "baseRefName": "main",
                                "headRefName": "feature/x",
                                "reviewThreads": {
                                    "nodes": [
                                        {
                                            "id": "T1",
                                            "isResolved": False,
                                            "isOutdated": False,
                                            "path": "a.py",
                                            "comments": {"nodes": [{"author": {"login": "bot"}, "body": "x"}]},
                                        }
                                    ]
                                },
                            }
                        }
                    }
                },
            }
        )
        with patch("plate_core.pr_verify.fetch_required_check_contexts", return_value=frozenset()):
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


class TestRunUnittestDiscover(unittest.TestCase):
    def test_parses_count_and_stale_warning(self):
        class _Result:
            returncode = 0
            stdout = "Ran 1210 tests in 10s\nOK"
            stderr = ""

        report = run_unittest_discover(runner=lambda *a, **k: _Result())
        self.assertEqual(report["test_count"], 1210)
        self.assertTrue(report["stale_base_warning"])


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
