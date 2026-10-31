"""Tests for gh plate ci audit (#1282)."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock

from plate_core.ci_audit import (
    _list_jobs_for_run,
    cache_visibility_from_steps,
    format_ci_audit_text,
    is_setup_step_name,
    is_test_step_name,
    job_waiting_seconds,
    run_ci_audit,
    split_step_seconds,
)
from plate_core.github_client import GhApiError
from plate_core.cli import main


def _step(name: str, number: int, start: str, end: str) -> dict:
    return {
        "name": name,
        "number": number,
        "status": "completed",
        "conclusion": "success",
        "started_at": start,
        "completed_at": end,
    }


class CiAuditHeuristicTests(unittest.TestCase):
    def test_setup_name_detection(self):
        self.assertTrue(is_setup_step_name("Checkout repository"))
        self.assertTrue(is_setup_step_name("Set up Python"))
        self.assertTrue(is_setup_step_name("Install dependencies"))
        self.assertTrue(is_setup_step_name("Cache pip"))
        self.assertFalse(is_setup_step_name("Run unit tests"))

    def test_test_name_detection(self):
        self.assertTrue(is_test_step_name("Run unit tests"))
        self.assertTrue(is_test_step_name("pytest -q"))
        self.assertFalse(is_test_step_name("Install dependencies"))

    def test_split_step_seconds_before_first_test(self):
        steps = [
            _step("Checkout", 1, "2026-01-01T12:00:00Z", "2026-01-01T12:01:00Z"),
            _step("Install deps", 2, "2026-01-01T12:01:00Z", "2026-01-01T12:03:00Z"),
            _step("Select runs-on", 3, "2026-01-01T12:03:00Z", "2026-01-01T12:04:00Z"),
            _step("Run unit tests", 4, "2026-01-01T12:04:00Z", "2026-01-01T12:10:00Z"),
            _step("Upload artifacts", 5, "2026-01-01T12:10:00Z", "2026-01-01T12:11:00Z"),
        ]
        setup_secs, running_secs = split_step_seconds(steps)
        self.assertEqual(setup_secs, 180.0)  # checkout + install only
        self.assertEqual(running_secs, 480.0)  # select + test + upload

    def test_job_waiting_seconds(self):
        job = {
            "created_at": "2026-01-01T12:00:00Z",
            "started_at": "2026-01-01T12:02:00Z",
        }
        self.assertEqual(job_waiting_seconds(job), 120.0)

    def test_cache_hints_from_step_names(self):
        hints = cache_visibility_from_steps(
            [
                {"name": "Cache pip dependencies (cache hit)"},
                {"name": "Restore cache miss fallback"},
            ]
        )
        self.assertEqual(hints, ["hint_hit", "hint_miss"])

    def test_cache_operation_names_are_not_hit_or_miss_hints(self):
        hints = cache_visibility_from_steps(
            [
                {"name": "Cache restore"},
                {"name": "Cache save"},
                {"name": "Cache pip dependencies"},
            ]
        )
        self.assertEqual(hints, ["hint_cache_step", "hint_cache_step", "hint_cache_step"])


class CiAuditReportTests(unittest.TestCase):
    def _mock_client(self):
        runs = [
            {
                "id": 9001,
                "name": "ci",
                "run_number": 42,
                "path": ".github/workflows/ci.yml",
            }
        ]
        jobs = [
            {
                "id": 11,
                "name": "test",
                "conclusion": "success",
                "created_at": "2026-01-01T12:00:00Z",
                "started_at": "2026-01-01T12:01:00Z",
                "completed_at": "2026-01-01T12:12:00Z",
                "steps": [
                    _step("Checkout", 1, "2026-01-01T12:01:00Z", "2026-01-01T12:02:00Z"),
                    _step("Cache pip (cache hit)", 2, "2026-01-01T12:02:00Z", "2026-01-01T12:03:00Z"),
                    _step("Run unit tests", 3, "2026-01-01T12:03:00Z", "2026-01-01T12:10:00Z"),
                ],
            }
        ]

        client = MagicMock()

        def api(endpoint, method="GET", fields=None, **kwargs):
            if endpoint.endswith("/actions/runs") and "/jobs" not in endpoint:
                return {"workflow_runs": runs}
            if endpoint.endswith("/actions/runs/9001/jobs"):
                return {"jobs": jobs}
            raise AssertionError(f"unexpected endpoint: {endpoint}")

        client.api.side_effect = api
        return client

    def test_run_ci_audit_builds_costliest_and_json_fields(self):
        report = run_ci_audit("acme/app", limit=1, client=self._mock_client())
        self.assertTrue(report.ok)
        self.assertEqual(report.repo, "acme/app")
        self.assertEqual(report.workflow_runs_fetched, 1)
        self.assertEqual(len(report.job_instances), 1)
        row = report.job_instances[0]
        self.assertEqual(row.waiting_seconds, 60.0)
        self.assertEqual(row.setup_seconds, 120.0)
        self.assertEqual(row.running_seconds, 420.0)
        self.assertIn("hint_hit", row.cache_hints)
        self.assertEqual(report.costliest_jobs[0].cache_hits, 1)
        payload = report.to_dict()
        self.assertIn("costliest_jobs", payload)
        self.assertIn("cache_hints_disclaimer", payload)
        self.assertEqual(payload["job_instances"][0]["total_minutes"], 10.0)
        self.assertEqual(len(report.costliest_jobs), 1)

    def test_job_list_pagination_collects_all_pages(self):
        client = MagicMock()
        calls: list[dict] = []

        def api(endpoint, method="GET", fields=None, **kwargs):
            if endpoint.endswith("/actions/runs/9001/jobs"):
                page = (fields or {}).get("page", 1)
                calls.append(page)
                if page == 1:
                    jobs = [{"id": i, "name": f"job-{i}", "steps": []} for i in range(100)]
                    return {"jobs": jobs}
                if page == 2:
                    return {"jobs": [{"id": 100, "name": "job-100", "steps": []}]}
                return {"jobs": []}
            raise AssertionError(endpoint)

        client.api.side_effect = api
        jobs = _list_jobs_for_run(client, "acme", "app", 9001)
        self.assertEqual(len(jobs), 101)
        self.assertEqual(calls, [1, 2])

    def test_job_fetch_failure_is_not_ok(self):
        runs = [{"id": 9001, "name": "ci", "run_number": 1}]

        def api(endpoint, method="GET", fields=None, **kwargs):
            if endpoint.endswith("/actions/runs") and "/jobs" not in endpoint:
                return {"workflow_runs": runs}
            if endpoint.endswith("/actions/runs/9001/jobs"):
                raise GhApiError("rate limited")
            raise AssertionError(endpoint)

        client = MagicMock()
        client.api.side_effect = api
        report = run_ci_audit("acme/app", limit=1, client=client)
        self.assertFalse(report.ok)
        self.assertEqual(report.error, "job_fetch_failed")
        self.assertEqual(report.failed_run_id, 9001)
        self.assertIn("9001", report.message or "")

    def test_cli_exits_nonzero_on_job_fetch_failure(self):
        runs = [{"id": 9001, "name": "ci", "run_number": 1}]

        def api(endpoint, method="GET", fields=None, **kwargs):
            if endpoint.endswith("/actions/runs") and "/jobs" not in endpoint:
                return {"workflow_runs": runs}
            if endpoint.endswith("/actions/runs/9001/jobs"):
                raise GhApiError("forbidden")
            raise AssertionError(endpoint)

        client = MagicMock()
        client.api.side_effect = api
        with unittest.mock.patch("plate_core.ci_audit.resolve_repo", return_value="acme/app"):
            with unittest.mock.patch("plate_core.ci_audit.GhClient", return_value=client):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = main(["ci", "audit", "--repo", "acme/app", "--limit", "1", "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out.getvalue().strip())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["failed_run_id"], 9001)

    def test_format_text_mentions_repo(self):
        report = run_ci_audit("acme/app", limit=1, client=self._mock_client())
        text = format_ci_audit_text(report)
        self.assertIn("Repo: acme/app", text)
        self.assertIn("ci / test", text)

    def test_cli_json_output(self):
        client = self._mock_client()
        with unittest.mock.patch("plate_core.ci_audit.resolve_repo", return_value="acme/app"):
            with unittest.mock.patch("plate_core.ci_audit.GhClient", return_value=client):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = main(["ci", "audit", "--repo", "acme/app", "--limit", "1", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["repo"], "acme/app")


if __name__ == "__main__":
    unittest.main()
