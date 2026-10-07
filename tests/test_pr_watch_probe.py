import json
import tempfile
import unittest
from pathlib import Path

from plate_core.pr_watch_probe import (
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
        self.assertEqual(p, Path("/tmp/root/.agentic/babysit/octo-repo-42.probe.json"))

    def test_probe_304_unchanged_single_request(self):
        state = ProbeState(etag='W/"etag1"', head_sha="abc", updated_at="t1", mergeable_state="clean")
        http = _RecordingHttp(
            {
                (
                    "/repos/o/r/pulls/1",
                    frozenset({("If-None-Match", 'W/"etag1"')}),
                ): (304, {}, None),
            }
        )
        result = probe_pr(http, "o/r", 1, state)
        self.assertTrue(result.not_modified)
        self.assertFalse(result.changed)
        self.assertIsNone(result.pr)
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.calls[0][0], "/repos/o/r/pulls/1")

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
                ("/repos/o/r/commits/sha2/status", frozenset()): (200, {}, {"state": "failure"}),
            }
        )
        result = probe_pr(http, "o/r", 3, state)
        self.assertTrue(result.changed)
        self.assertEqual(result.new_state.ci_state, "failure")
        self.assertEqual(result.new_state.mergeable_state, "unstable")

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
                    "/repos/o/r/issues/4/comments?since=2026-01-01T12:00:00Z",
                    frozenset(),
                ): (200, {}, [{"id": 99}, {"id": 101, "body": "hi"}]),
                (
                    "/repos/o/r/pulls/4/comments?since=2026-01-01T12:00:00Z",
                    frozenset(),
                ): (200, {}, [{"id": 201}]),
                ("/repos/o/r/pulls/4/reviews", frozenset()): (
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


if __name__ == "__main__":
    unittest.main()
