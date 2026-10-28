"""Tests for PR babysit --watch guards (#1233)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from plate_core.github_client import GhApiError
from plate_core.pr_babysit import (
    _load_pr_data,
    evaluate_babysit_gates,
    get_unresolved_review_threads,
)
from plate_core.pr_watch_guards import (
    apply_ci_guards_to_probe,
    apply_settle_before_finished,
    ci_read_fingerprint,
    compute_raw_ci_state,
    fetch_required_check_contexts,
    is_graphql_rate_limited,
    load_pr_data_rest_fallback,
    missing_required_contexts,
    observed_check_contexts,
    review_decision_from_rest_reviews,
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
                        "target": "branch",
                        "conditions": {
                            "ref_name": {"include": ["refs/heads/main"], "exclude": []},
                        },
                        "rules": [
                            {
                                "type": "required_status_checks",
                                "parameters": {
                                    "required_status_checks": [{"context": "pr-gates"}],
                                },
                            }
                        ],
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
        second = apply_settle_before_finished(
            "success",
            fp,
            prior_fingerprint=fp,
            prior_streak=first[2],
            prior_ci_state="pending",
        )
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
            prior_ci_state=None,
        )
        self.assertEqual(reported, "pending")
        reported2, _, _ = apply_ci_guards_to_probe(
            status_json=status,
            check_runs=runs,
            required_contexts=frozenset(),
            prior_fingerprint=fingerprint,
            prior_streak=streak,
            prior_ci_state="pending",
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
            if "rulesets" in endpoint:
                return []
            if endpoint.startswith("repos/o/r/pulls/5/reviews"):
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


class CopilotRegressionTests(unittest.TestCase):
    def test_review_threads_unavailable_blocks_merge_gates(self):
        blocked = evaluate_babysit_gates(
            {
                "merge_state": "CLEAN",
                "unresolved_review_threads": 0,
                "review_threads_unavailable": True,
            }
        )
        self.assertTrue(blocked["blocked"])
        self.assertIn("unavailable", blocked["reason"].lower())

    def test_get_unresolved_raises_when_threads_unavailable(self):
        client = MagicMock()

        def api_router(endpoint, method="GET", fields=None, **kwargs):
            if endpoint == "graphql":
                raise GhApiError("GraphQL rate limit exceeded for api")
            if endpoint == "repos/o/r/pulls/3":
                return {"head": {"sha": "s"}, "base": {"ref": "main"}, "mergeable_state": "clean"}
            if endpoint.endswith("/status"):
                return {"state": "success", "total_count": 0, "statuses": []}
            if "check-runs" in endpoint:
                return {"check_runs": []}
            if "reviews" in endpoint:
                return []
            if "protection" in endpoint or "rulesets" in endpoint:
                raise GhApiError("404")
            return {}

        client.api.side_effect = api_router
        with self.assertRaises(GhApiError):
            get_unresolved_review_threads(3, repo="o/r", client=client)

    def test_rest_fallback_marks_review_threads_unavailable(self):
        client = MagicMock()

        def api_router(endpoint, method="GET", fields=None, **kwargs):
            if endpoint == "repos/o/r/pulls/4":
                return {"head": {"sha": "s"}, "base": {"ref": "main"}, "mergeable_state": "clean"}
            if endpoint.endswith("/status"):
                return {"state": "success", "total_count": 0, "statuses": []}
            if "check-runs" in endpoint:
                return {"check_runs": []}
            if "reviews" in endpoint:
                return []
            if "protection" in endpoint or "rulesets" in endpoint:
                raise GhApiError("404")
            return {}

        client.api.side_effect = api_router
        data = load_pr_data_rest_fallback(client, "o/r", 4)
        self.assertTrue(data.get("review_threads_unavailable"))

    def test_review_decision_keeps_outstanding_changes_requested(self):
        reviews = [
            {
                "id": 1,
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-01-01T00:00:00Z",
                "user": {"login": "alice"},
            },
            {
                "id": 2,
                "state": "APPROVED",
                "submitted_at": "2026-01-02T00:00:00Z",
                "user": {"login": "bob"},
            },
        ]
        self.assertEqual(review_decision_from_rest_reviews(reviews), "CHANGES_REQUESTED")

    def test_review_decision_ignores_dismissed_latest(self):
        reviews = [
            {
                "id": 1,
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-01-01T00:00:00Z",
                "user": {"login": "alice"},
            },
            {
                "id": 2,
                "state": "DISMISSED",
                "submitted_at": "2026-01-02T00:00:00Z",
                "user": {"login": "alice"},
            },
            {
                "id": 3,
                "state": "APPROVED",
                "submitted_at": "2026-01-03T00:00:00Z",
                "user": {"login": "bob"},
            },
        ]
        self.assertEqual(review_decision_from_rest_reviews(reviews), "APPROVED")

    def test_fingerprint_includes_head_sha(self):
        runs = [{"name": "test", "status": "completed", "conclusion": "success"}]
        status = {"state": "success", "total_count": 1}
        fp_a = ci_read_fingerprint(status, runs, missing_required=[], head_sha="aaa")
        fp_b = ci_read_fingerprint(status, runs, missing_required=[], head_sha="bbb")
        self.assertNotEqual(fp_a, fp_b)

    def test_new_head_defers_success_despite_prior_settle(self):
        runs = [{"name": "test", "status": "completed", "conclusion": "success"}]
        status = {"state": "success", "total_count": 1}
        settled = ProbeState(
            head_sha="oldsha",
            ci_state="success",
            ci_settle_fingerprint="ignored",
            ci_settle_streak=5,
            required_contexts=[],
        )

        class _HeadHttp:
            def get(self, path: str, headers=None):
                if path.endswith("/pulls/9"):
                    return (
                        200,
                        {"ETag": 'W/"e"'},
                        {
                            "head": {"sha": "newsha"},
                            "base": {"ref": "main"},
                            "updated_at": "t2",
                            "mergeable_state": "clean",
                        },
                    )
                if path.endswith("/status"):
                    return 200, {}, status
                if "check-runs" in path:
                    return 200, {}, {"check_runs": runs}
                if "protection" in path or "rulesets" in path:
                    return 404, {}, None
                return 404, {}, None

        result = probe_pr(_HeadHttp(), "o/r", 9, settled)
        self.assertEqual(result.new_state.ci_state, "pending")

    def test_ruleset_skips_evaluate_and_other_branch(self):
        http = _RecordingHttp(
            {
                "/repos/o/r/branches/main/protection": (404, {}, None),
                "/repos/o/r/rulesets?per_page=100": (
                    200,
                    {},
                    [
                        {"id": 1, "enforcement": "evaluate", "target": "branch"},
                        {"id": 2, "enforcement": "active", "target": "branch"},
                    ],
                ),
                "/repos/o/r/rulesets/2": (
                    200,
                    {},
                    {
                        "target": "branch",
                        "conditions": {
                            "ref_name": {"include": ["refs/heads/release"], "exclude": []},
                        },
                        "rules": [
                            {
                                "type": "required_status_checks",
                                "parameters": {
                                    "required_status_checks": [{"context": "wrong-branch"}],
                                },
                            }
                        ],
                    },
                ),
            }
        )
        contexts = fetch_required_check_contexts(http, "o/r", "main")
        self.assertEqual(contexts, frozenset())

    def test_empty_status_aggregate_uses_check_runs(self):
        raw = compute_raw_ci_state(
            {"state": "pending", "total_count": 0, "statuses": []},
            [{"name": "ci", "status": "completed", "conclusion": "success"}],
            missing_required=[],
        )
        self.assertEqual(raw, "success")

    def test_probe_caches_empty_required_contexts_on_304(self):
        class _KeyedHttp:
            def __init__(self):
                self.calls: list[str] = []

            def get(self, path: str, headers=None):
                self.calls.append(path)
                headers = dict(headers or {})
                if path == "/repos/o/r/pulls/7":
                    if headers.get("If-None-Match") == 'W/"etag7"':
                        return 304, {}, None
                    return (
                        200,
                        {"ETag": 'W/"etag7"'},
                        {
                            "head": {"sha": "sha"},
                            "base": {"ref": "main"},
                            "updated_at": "t1",
                            "mergeable_state": "clean",
                        },
                    )
                if path == "/repos/o/r/branches/main/protection":
                    return 404, {}, None
                if path == "/repos/o/r/rulesets?per_page=100":
                    return 200, {}, []
                if path == "/repos/o/r/commits/sha/status":
                    return 200, {}, {"state": "success", "total_count": 0}
                if path.startswith("/repos/o/r/commits/sha/check-runs"):
                    return (
                        200,
                        {},
                        {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]},
                    )
                return 404, {}, None

        http = _KeyedHttp()
        first = probe_pr(http, "o/r", 7, None)
        self.assertEqual(first.new_state.required_contexts, [])
        protection_calls = [path for path in http.calls if "protection" in path or "rulesets" in path]
        self.assertEqual(len(protection_calls), 2)

        http.calls.clear()
        second = probe_pr(http, "o/r", 7, first.new_state)
        self.assertTrue(second.not_modified)
        refetch_calls = [path for path in http.calls if "protection" in path or "rulesets" in path]
        self.assertEqual(refetch_calls, [])

    def test_probe_persists_empty_required_after_retarget(self):
        http = _RecordingHttp(
            {
                "/repos/o/r/pulls/8": (
                    200,
                    {},
                    {
                        "head": {"sha": "sha"},
                        "base": {"ref": "unprotected"},
                        "updated_at": "t2",
                        "mergeable_state": "clean",
                    },
                ),
                "/repos/o/r/branches/unprotected/protection": (404, {}, None),
                "/repos/o/r/rulesets?per_page=100": (200, {}, []),
                "/repos/o/r/commits/sha/status": (200, {}, {"state": "success", "total_count": 0}),
                "/repos/o/r/commits/sha/check-runs?per_page=100&page=1": (
                    200,
                    {},
                    {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]},
                ),
            }
        )
        prior = ProbeState(
            base_ref="main",
            required_contexts=["pr-gates"],
            head_sha="sha",
            etag='W/"etag"',
            ci_state="pending",
        )
        result = probe_pr(http, "o/r", 8, prior)
        self.assertEqual(result.new_state.base_ref, "unprotected")
        self.assertEqual(result.new_state.required_contexts, [])


if __name__ == "__main__":
    unittest.main()
