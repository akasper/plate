"""Tests for PR babysit --watch guards (#1233)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from plate_core.github_client import GhApiError
from plate_core.pr_babysit import _load_pr_data
from plate_core.pr_watch_guards import (
    apply_ci_guards_to_probe,
    apply_settle_before_finished,
    compute_raw_ci_state,
    fetch_required_check_contexts,
    is_graphql_rate_limited,
    load_pr_data_rest_fallback,
    missing_required_contexts,
    observed_check_contexts,
)
from plate_core.pr_watch_probe import ProbeState, probe_pr


class _RecordingHttp:
    def __init__(self, responses: dict[str, tuple[int, dict, object]]):
        self._responses = responses
        self.calls: list[str] = []

    def get(self, path: str, headers=None):
        self.calls.append(path)
        if path not in self._responses:
            return 404, {}, None
        return self._responses[path]


class RequiredChecksFirstTests(unittest.TestCase):
    def test_missing_required_context_counts_as_pending(self):
        raw = compute_raw_ci_state(
            {"state": "success"},
            [{"name": "lint", "status": "completed", "conclusion": "success"}],
            missing_required=["pr-gates"],
        )
        self.assertEqual(raw, "pending")

    def test_fetch_required_from_protection_and_rulesets(self):
        http = _RecordingHttp(
            {
                "/repos/o/r/branches/main/protection": (
                    200,
                    {},
                    {"required_status_checks": {"contexts": ["labels"]}},
                ),
                "/repos/o/r/rulesets?per_page=100": (
                    200,
                    {},
                    [{"id": 9, "enforcement": "active"}],
                ),
                "/repos/o/r/rulesets/9": (
                    200,
                    {},
                    {
                        "rules": [
                            {
                                "type": "required_status_checks",
                                "parameters": {
                                    "required_status_checks": [{"context": "pr-gates"}],
                                },
                            }
                        ]
                    },
                ),
            }
        )
        contexts = fetch_required_check_contexts(http, "o/r", "main")
        self.assertEqual(contexts, frozenset({"labels", "pr-gates"}))

    def test_probe_marks_missing_required_as_pending(self):
        http = _RecordingHttp(
            {
                "/repos/o/r/pulls/1": (
                    200,
                    {},
                    {
                        "head": {"sha": "abc"},
                        "base": {"ref": "main"},
                        "updated_at": "t1",
                        "mergeable_state": "clean",
                    },
                ),
                "/repos/o/r/branches/main/protection": (
                    200,
                    {},
                    {"required_status_checks": {"contexts": ["pr-gates"]}},
                ),
                "/repos/o/r/rulesets?per_page=100": (200, {}, []),
                "/repos/o/r/commits/abc/status": (200, {}, {"state": "success"}),
                "/repos/o/r/commits/abc/check-runs?per_page=100&page=1": (
                    200,
                    {},
                    {"check_runs": [{"name": "lint", "status": "completed", "conclusion": "success"}]},
                ),
            }
        )
        result = probe_pr(http, "o/r", 1, None)
        self.assertEqual(result.new_state.ci_state, "pending")
        missing = missing_required_contexts(
            frozenset({"pr-gates"}),
            observed_check_contexts(
                {"state": "success"},
                [{"name": "lint", "status": "completed", "conclusion": "success"}],
            ),
        )
        self.assertEqual(missing, ["pr-gates"])


class SettleBeforeFinishedTests(unittest.TestCase):
    def test_success_requires_two_identical_reads(self):
        fp = "abc123"
        first = apply_settle_before_finished("success", fp, prior_fingerprint=None, prior_streak=0)
        self.assertEqual(first[0], "pending")
        second = apply_settle_before_finished("success", fp, prior_fingerprint=fp, prior_streak=first[2])
        self.assertEqual(second[0], "success")

    def test_probe_defers_success_until_second_identical_read(self):
        responses = {
            "/repos/o/r/pulls/2": (
                200,
                {},
                {
                    "head": {"sha": "sha"},
                    "base": {"ref": "main"},
                    "updated_at": "t1",
                    "mergeable_state": "clean",
                },
            ),
            "/repos/o/r/branches/main/protection": (404, {}, None),
            "/repos/o/r/rulesets?per_page=100": (200, {}, []),
            "/repos/o/r/commits/sha/status": (200, {}, {"state": "success"}),
            "/repos/o/r/commits/sha/check-runs?per_page=100&page=1": (
                200,
                {},
                {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]},
            ),
        }
        http = _RecordingHttp(responses)
        first = probe_pr(http, "o/r", 2, None)
        self.assertEqual(first.new_state.ci_state, "pending")
        second = probe_pr(http, "o/r", 2, first.new_state)
        self.assertEqual(second.new_state.ci_state, "success")

    def test_apply_ci_guards_unit(self):
        runs = [{"name": "test", "status": "completed", "conclusion": "success"}]
        status = {"state": "success"}
        reported, fingerprint, streak = apply_ci_guards_to_probe(
            status_json=status,
            check_runs=runs,
            required_contexts=frozenset(),
            prior_fingerprint=None,
            prior_streak=0,
        )
        self.assertEqual(reported, "pending")
        reported2, _, _ = apply_ci_guards_to_probe(
            status_json=status,
            check_runs=runs,
            required_contexts=frozenset(),
            prior_fingerprint=fingerprint,
            prior_streak=streak,
        )
        self.assertEqual(reported2, "success")


class GraphqlRestFallbackTests(unittest.TestCase):
    def test_is_graphql_rate_limited(self):
        self.assertTrue(is_graphql_rate_limited(GhApiError("GraphQL rate limit exceeded")))
        self.assertFalse(is_graphql_rate_limited(GhApiError("not found")))

    def test_load_pr_data_uses_rest_when_graphql_rate_limited(self):
        client = MagicMock()
        client.api.side_effect = [
            GhApiError("GraphQL rate limit exceeded for api"),
        ]

        def rest_api(endpoint, method="GET", fields=None, **kwargs):
            if endpoint == "repos/o/r/pulls/5":
                return {
                    "head": {"sha": "deadbeef", "ref": "feature"},
                    "base": {"ref": "main"},
                    "mergeable_state": "clean",
                }
            if endpoint == "repos/o/r/commits/deadbeef/status":
                return {"state": "success", "statuses": []}
            if endpoint.startswith("repos/o/r/commits/deadbeef/check-runs"):
                return {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]}
            if endpoint == "repos/o/r/branches/main/protection":
                raise GhApiError("404")
            if endpoint == "repos/o/r/rulesets":
                return []
            if endpoint == "repos/o/r/pulls/5/reviews":
                return [{"state": "APPROVED", "user": {"login": "human"}}]
            raise AssertionError(f"unexpected endpoint {endpoint}")

        client.api.side_effect = None
        calls: list[str] = []

        def api_router(endpoint, method="GET", fields=None, **kwargs):
            calls.append(endpoint)
            if endpoint == "graphql":
                raise GhApiError("GraphQL rate limit exceeded for api")
            return rest_api(endpoint, method, fields, **kwargs)

        client.api.side_effect = api_router
        data = _load_pr_data(client, "o/r", 5)
        self.assertTrue(data.get("rest_fallback"))
        self.assertEqual(data.get("mergeStateStatus"), "CLEAN")
        self.assertEqual(data.get("reviewDecision"), "APPROVED")
        self.assertEqual(data["statusCheckRollup"]["state"], "SUCCESS")
        self.assertIn("graphql", calls[0])

    def test_rest_fallback_helper_direct(self):
        client = MagicMock()

        def api_router(endpoint, method="GET", fields=None, **kwargs):
            if endpoint == "repos/o/r/pulls/1":
                return {"head": {"sha": "s"}, "base": {"ref": "main"}, "mergeable_state": "behind"}
            if endpoint.endswith("/status"):
                return {"state": "pending"}
            if "check-runs" in endpoint:
                return {"check_runs": []}
            if endpoint.endswith("/reviews"):
                return []
            if "protection" in endpoint or "rulesets" in endpoint:
                raise GhApiError("404")
            return {}

        client.api.side_effect = api_router
        data = load_pr_data_rest_fallback(client, "o/r", 1)
        self.assertTrue(data["rest_fallback"])
        self.assertEqual(data["mergeStateStatus"], "BEHIND")


if __name__ == "__main__":
    unittest.main()
