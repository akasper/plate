import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from plate_core.pr_watch_probe import (
    GhApiHttp,
    ProbeState,
    fetch_delta,
    load_probe_state,
    probe_pr,
    probe_state_path,
    save_probe_state,
)


class _RecordingHttp:
    def __init__(self, responses: dict[tuple[str, frozenset], tuple[int, dict, object]]):
        self._responses = responses
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, path: str, headers=None):
        self.calls.append((path, dict(headers or {})))
        key = (path, frozenset((headers or {}).items()))
        if key not in self._responses:
            # match path only when headers empty in table
            for (p, h), val in self._responses.items():
                if p == path and (not h or h == key[1]):
                    return val
        return self._responses[key]


class PrWatchProbeTests(unittest.TestCase):
    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.json"
            state = ProbeState(
                etag='W/"abc"',
                head_sha="sha1",
                updated_at="2026-01-01T00:00:00Z",
                mergeable_state="clean",
                ci_state="success",
                last_checked_at="2026-01-02T00:00:00Z",
                last_issue_comment_id=10,
                last_review_comment_id=20,
                last_review_id=3,
            )
            save_probe_state(path, state)
            loaded = load_probe_state(path)
            self.assertEqual(loaded, state)

    def test_probe_state_path(self):
        p = probe_state_path("octo/repo", 42, root="/tmp/root")
        self.assertEqual(p, Path("/tmp/root/.agentic/babysit/4-octo-4-repo-42.probe.json"))
        other = probe_state_path("oct-o/repo", 42, root="/tmp/root")
        self.assertNotEqual(p, other)
        self.assertNotEqual(
            probe_state_path("a-b/c", 42, root="/tmp/root"),
            probe_state_path("a/b-c", 42, root="/tmp/root"),
        )

    def test_probe_304_unchanged_pr_resource(self):
        state = ProbeState(etag='W/"etag1"', head_sha="abc", updated_at="t1", mergeable_state="clean", ci_state="success")
        http = _RecordingHttp(
            {
                (
                    "/repos/o/r/pulls/1",
                    frozenset({("If-None-Match", 'W/"etag1"')}),
                ): (304, {}, None),
                ("/repos/o/r/commits/abc/status", frozenset()): (200, {}, {"state": "success"}),
                (
                    "/repos/o/r/commits/abc/check-runs?per_page=100&page=1",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            }
        )
        result = probe_pr(http, "o/r", 1, state)
        self.assertTrue(result.not_modified)
        self.assertFalse(result.changed)
        self.assertIsNone(result.pr)
        self.assertEqual(len(http.calls), 3)
        self.assertEqual(http.calls[0][0], "/repos/o/r/pulls/1")

    def test_gh_api_http_accepts_nonzero_304_response(self):
        proc = SimpleNamespace(
            returncode=1,
            stdout="HTTP/2.0 304 Not Modified\r\nETag: W/\"same\"\r\n\r\n",
            stderr="gh: HTTP 304",
        )
        with patch("plate_core.pr_watch_probe.run_hidden", return_value=proc):
            status, headers, body = GhApiHttp().get("/repos/o/r/pulls/1")
        self.assertEqual(status, 304)
        self.assertEqual(headers["ETag"], 'W/"same"')
        self.assertEqual(body, {})

    def test_probe_check_run_transition_on_304_same_head(self):
        state = ProbeState(
            etag='W/"etag1"',
            head_sha="abc",
            updated_at="t1",
            mergeable_state="clean",
            ci_state="pending",
        )
        http = _RecordingHttp(
            {
                ("/repos/o/r/pulls/1", frozenset({("If-None-Match", 'W/"etag1"')})): (304, {}, None),
                ("/repos/o/r/commits/abc/status", frozenset()): (200, {}, {"state": "success"}),
                (
                    "/repos/o/r/commits/abc/check-runs?per_page=100&page=1",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            }
        )
        result = probe_pr(http, "o/r", 1, state)
        self.assertTrue(result.not_modified)
        self.assertTrue(result.changed)
        self.assertEqual(result.new_state.ci_state, "success")

    def test_probe_new_commit_fetches_status(self):
        state = ProbeState(
            etag='W/"old"',
            head_sha="oldsha",
            updated_at="2026-01-01T00:00:00Z",
            mergeable_state="clean",
            ci_state="pending",
        )
        http = _RecordingHttp(
            {
                ("/repos/o/r/pulls/2", frozenset({("If-None-Match", 'W/"old"')})): (
                    200,
                    {"etag": 'W/"new"'},
                    {
                        "head": {"sha": "newsha"},
                        "updated_at": "2026-01-02T00:00:00Z",
                        "mergeable_state": "clean",
                    },
                ),
                ("/repos/o/r/commits/newsha/status", frozenset()): (
                    200,
                    {},
                    {"state": "success"},
                ),
                (
                    "/repos/o/r/commits/newsha/check-runs?per_page=100&page=1",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            }
        )
        result = probe_pr(http, "o/r", 2, state)
        self.assertFalse(result.not_modified)
        self.assertTrue(result.changed)
        self.assertEqual(result.new_state.head_sha, "newsha")
        self.assertEqual(result.new_state.ci_state, "success")
        paths = [c[0] for c in http.calls]
        self.assertEqual(paths[0], "/repos/o/r/pulls/2")
        self.assertIn("/repos/o/r/commits/newsha/status", paths)

    def test_probe_ci_transition_on_head_change(self):
        state = ProbeState(head_sha="sha", updated_at="t1", ci_state="pending")
        http = _RecordingHttp(
            {
                ("/repos/o/r/pulls/3", frozenset()): (
                    200,
                    {"ETag": 'W/"e"'},
                    {
                        "head": {"sha": "sha2"},
                        "updated_at": "t2",
                        "mergeable_state": "unstable",
                    },
                ),
                ("/repos/o/r/commits/sha2/status", frozenset()): (200, {}, {"state": "success"}),
                (
                    "/repos/o/r/commits/sha2/check-runs?per_page=100&page=1",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": [{"status": "completed", "conclusion": "failure"}]}),
            }
        )
        result = probe_pr(http, "o/r", 3, state)
        self.assertTrue(result.changed)
        self.assertEqual(result.new_state.ci_state, "failure")
        self.assertEqual(result.new_state.mergeable_state, "unstable")

    def test_probe_paginates_check_runs(self):
        successful_runs = [{"status": "completed", "conclusion": "success"} for _ in range(100)]
        http = _RecordingHttp(
            {
                ("/repos/o/r/pulls/5", frozenset()): (
                    200,
                    {},
                    {"head": {"sha": "sha"}, "updated_at": "t1", "mergeable_state": "clean"},
                ),
                ("/repos/o/r/commits/sha/status", frozenset()): (200, {}, {"state": "success"}),
                (
                    "/repos/o/r/commits/sha/check-runs?per_page=100&page=1",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": successful_runs}),
                (
                    "/repos/o/r/commits/sha/check-runs?per_page=100&page=2",
                    frozenset({("Accept", "application/vnd.github+json")}),
                ): (200, {}, {"check_runs": [{"status": "completed", "conclusion": "failure"}]}),
            }
        )
        result = probe_pr(http, "o/r", 5, None)
        self.assertEqual(result.new_state.ci_state, "failure")
        self.assertEqual(
            [path for path, _ in http.calls if "check-runs" in path],
            [
                "/repos/o/r/commits/sha/check-runs?per_page=100&page=1",
                "/repos/o/r/commits/sha/check-runs?per_page=100&page=2",
            ],
        )

    def test_checkpoint_is_recorded_before_request(self):
        events = []

        class OrderedHttp:
            def get(self, path, headers=None):
                events.append("request")
                return 304, {}, None

        with patch("plate_core.pr_watch_probe._utc_now_iso", side_effect=lambda: events.append("checkpoint") or "t0"):
            result = probe_pr(OrderedHttp(), "o/r", 1, ProbeState(etag='W/"etag"'))
        self.assertEqual(events, ["checkpoint", "request"])
        self.assertEqual(result.new_state.last_checked_at, "t0")

    def test_fetch_delta_new_comment(self):
        state = ProbeState(
            last_checked_at="2026-01-01T12:00:00Z",
            last_issue_comment_id=100,
            last_review_comment_id=200,
            last_review_id=5,
        )
        http = _RecordingHttp(
            {
                (
                    "/repos/o/r/issues/4/comments?since=2026-01-01T12:00:00Z&per_page=100&page=1",
                    frozenset(),
                ): (200, {}, [{"id": 99}, {"id": 101, "body": "hi"}]),
                (
                    "/repos/o/r/pulls/4/comments?since=2026-01-01T12:00:00Z&per_page=100&page=1",
                    frozenset(),
                ): (200, {}, [{"id": 201}]),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=1", frozenset()): (
                    200,
                    {},
                    [{"id": 5}, {"id": 6, "state": "COMMENTED"}],
                ),
            }
        )
        delta = fetch_delta(http, "o/r", 4, state)
        self.assertEqual([c["id"] for c in delta["issue_comments"]], [101])
        self.assertEqual([c["id"] for c in delta["review_comments"]], [201])
        self.assertEqual([r["id"] for r in delta["reviews"]], [6])
        self.assertEqual(delta["new_state"].last_issue_comment_id, 101)
        self.assertEqual(delta["new_state"].last_review_comment_id, 201)
        self.assertEqual(delta["new_state"].last_review_id, 6)
        self.assertEqual(state.last_issue_comment_id, 100)

    def test_fetch_delta_paginates_issue_and_review_comments(self):
        since = "1970-01-01T00:00:00Z"
        issue_page_1 = [{"id": i} for i in range(1, 101)]
        issue_page_2 = [{"id": 101}, {"id": 102}]
        review_page_1 = [{"id": i} for i in range(1, 101)]
        review_page_2 = [{"id": 150}]
        http = _RecordingHttp(
            {
                (f"/repos/o/r/issues/4/comments?since={since}&per_page=100&page=1", frozenset()): (
                    200,
                    {},
                    issue_page_1,
                ),
                (f"/repos/o/r/issues/4/comments?since={since}&per_page=100&page=2", frozenset()): (
                    200,
                    {},
                    issue_page_2,
                ),
                (f"/repos/o/r/pulls/4/comments?since={since}&per_page=100&page=1", frozenset()): (
                    200,
                    {},
                    review_page_1,
                ),
                (f"/repos/o/r/pulls/4/comments?since={since}&per_page=100&page=2", frozenset()): (
                    200,
                    {},
                    review_page_2,
                ),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=1", frozenset()): (200, {}, []),
            }
        )
        delta = fetch_delta(http, "o/r", 4, ProbeState())
        self.assertEqual(len(delta["issue_comments"]), 102)
        self.assertEqual(delta["issue_comments"][-1]["id"], 102)
        self.assertEqual(delta["review_comments"][-1]["id"], 150)
        self.assertEqual(delta["new_state"].last_issue_comment_id, 102)
        self.assertEqual(delta["new_state"].last_review_comment_id, 150)

    def test_fetch_delta_paginates_reviews(self):
        empty = (200, {}, [])
        first_page = [{"id": i} for i in range(1, 101)]
        second_page = [{"id": i} for i in range(101, 201)]
        http = _RecordingHttp(
            {
                ("/repos/o/r/issues/4/comments?since=1970-01-01T00:00:00Z&per_page=100&page=1", frozenset()): empty,
                ("/repos/o/r/pulls/4/comments?since=1970-01-01T00:00:00Z&per_page=100&page=1", frozenset()): empty,
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=1", frozenset()): (200, {}, first_page),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=2", frozenset()): (200, {}, second_page),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=3", frozenset()): (200, {}, [{"id": 201}]),
            }
        )
        delta = fetch_delta(http, "o/r", 4, ProbeState(last_review_id=99))
        self.assertEqual(len(delta["reviews"]), 102)
        self.assertEqual(delta["reviews"][0]["id"], 100)
        self.assertEqual(delta["reviews"][-1]["id"], 201)
        self.assertEqual([call[0] for call in http.calls][-3:], [
            "/repos/o/r/pulls/4/reviews?per_page=100&page=1",
            "/repos/o/r/pulls/4/reviews?per_page=100&page=2",
            "/repos/o/r/pulls/4/reviews?per_page=100&page=3",
        ])

    def test_fetch_delta_reads_recent_review_pages_until_cursor(self):
        empty = (200, {}, [])
        first_page = [{"id": i} for i in range(1, 101)]
        second_page = [{"id": i} for i in range(101, 201)]
        third_page = [{"id": 201}, {"id": 202}]
        http = _RecordingHttp(
            {
                ("/repos/o/r/issues/4/comments?since=1970-01-01T00:00:00Z&per_page=100&page=1", frozenset()): empty,
                ("/repos/o/r/pulls/4/comments?since=1970-01-01T00:00:00Z&per_page=100&page=1", frozenset()): empty,
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=1", frozenset()): (
                    200,
                    {"Link": '<https://api.github.com/repos/o/r/pulls/4/reviews?per_page=100&page=3>; rel="last"'},
                    first_page,
                ),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=2", frozenset()): (200, {}, second_page),
                ("/repos/o/r/pulls/4/reviews?per_page=100&page=3", frozenset()): (200, {}, third_page),
            }
        )
        delta = fetch_delta(http, "o/r", 4, ProbeState(last_review_id=199))
        self.assertEqual([review["id"] for review in delta["reviews"]], [200, 201, 202])
        review_calls = [path for path, _ in http.calls if "/reviews?" in path]
        self.assertEqual(
            review_calls,
            [
                "/repos/o/r/pulls/4/reviews?per_page=100&page=1",
                "/repos/o/r/pulls/4/reviews?per_page=100&page=3",
                "/repos/o/r/pulls/4/reviews?per_page=100&page=2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
