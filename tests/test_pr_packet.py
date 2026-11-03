"""Tests for gh plate pr-packet / plate_pr_packet (#1364)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from plate_core.pr_packet import (
    DEFAULT_MAX_BYTES,
    PrPacketResult,
    _comment_snippet,
    _extract_fail_lines_from_log,
    _format_thread_nodes,
    _load_pr_graphql,
    _quoted_code_lines,
    _summarize_check_runs,
    _thread_state,
    assemble_packet,
    build_pr_packet,
    packet_probe_state_path,
    serialize_pr_packet,
)
from plate_core.pr_watch_probe import ProbeResult, ProbeState, probe_state_path, save_probe_state


FIXTURE_GRAPHQL = {
    "body": "Ship it.\n\nCloses #1364\nFixes #100",
    "mergeStateStatus": "BEHIND",
    "baseRefName": "main",
    "headRefOid": "abc123",
    "labels": ["Feature", "area:agent"],
    "milestone": "Agent crews",
    "reviewThreads": [
        {
            "id": "thread-unresolved",
            "isResolved": False,
            "isOutdated": False,
            "path": "src/foo.py",
            "line": 10,
            "comments": {
                "totalCount": 1,
                "nodes": [
                    {
                        "body": "Please fix this " + ("x" * 500),
                        "path": "src/foo.py",
                        "line": 10,
                        "diffHunk": "@@ -8,3 +8,3 @@\n old\n-old line\n+new line",
                        "author": {"login": "copilot-pull-request-reviewer"},
                    }
                ],
            },
        },
        {
            "id": "thread-outdated",
            "isResolved": False,
            "isOutdated": True,
            "path": "src/bar.py",
            "line": 3,
            "comments": {
                "totalCount": 1,
                "nodes": [
                    {
                        "body": "Stale comment",
                        "diffHunk": "@@ -1 +1 @@\n-a\n+b",
                        "author": {"login": "cursor[bot]"},
                    }
                ],
            },
        },
        {
            "id": "thread-addressed",
            "isResolved": False,
            "isOutdated": False,
            "path": "src/baz.py",
            "line": 1,
            "comments": {
                "totalCount": 2,
                "nodes": [
                    {
                        "body": "First",
                        "author": {"login": "human"},
                    },
                    {
                        "body": "Follow-up reply",
                        "author": {"login": "human"},
                    },
                ],
            },
        },
    ],
}


class PrPacketUnitTests(unittest.TestCase):
    def test_thread_state_rules(self):
        self.assertEqual(_thread_state(is_outdated=True, is_resolved=False, comment_count=1), "outdated")
        self.assertEqual(_thread_state(is_outdated=False, is_resolved=False, comment_count=2), "addressed")
        self.assertEqual(_thread_state(is_outdated=False, is_resolved=True, comment_count=1), "addressed")
        self.assertEqual(_thread_state(is_outdated=False, is_resolved=False, comment_count=1), "unresolved")

    def test_comment_snippet_truncates(self):
        self.assertEqual(_comment_snippet("short"), "short")
        long = "a" * 500
        self.assertTrue(_comment_snippet(long).endswith("…"))
        self.assertEqual(len(_comment_snippet(long)), 400 + 1)

    def test_format_thread_nodes(self):
        nodes = _format_thread_nodes(FIXTURE_GRAPHQL["reviewThreads"])
        by_id = {n["id"]: n for n in nodes}
        self.assertEqual(by_id["thread-unresolved"]["state"], "unresolved")
        self.assertEqual(by_id["thread-outdated"]["state"], "outdated")
        self.assertEqual(by_id["thread-addressed"]["state"], "addressed")
        self.assertTrue(by_id["thread-unresolved"]["quoted_code_lines"])

    def test_quoted_code_lines_window_around_thread_line(self):
        lines = [" context"]
        hunk_header = "@@ -1,60 +1,60 @@"
        for i in range(2, 62):
            prefix = "+" if i == 50 else " "
            lines.append(f"{prefix}line-{i}")
        diff_hunk = hunk_header + "\n" + "\n".join(lines)
        quoted = _quoted_code_lines(diff_hunk, line=50)
        joined = "\n".join(quoted)
        self.assertIn("line-50", joined)
        self.assertNotIn("line-2", joined)
        self.assertLessEqual(len(quoted), 12)

    def test_summarize_check_runs_includes_failure_excerpt(self):
        checks = _summarize_check_runs(
            [
                {"name": "ok", "conclusion": "success"},
                {
                    "name": "unit",
                    "conclusion": "failure",
                    "output": {"text": "FAILED test_one\nAssertionError\n\nmore noise"},
                },
            ]
        )
        self.assertEqual(len(checks), 2)
        self.assertIn("log_excerpt", checks[1])
        self.assertIn("FAILED", checks[1]["log_excerpt"][0])

    def test_summarize_check_runs_fetches_actions_job_log_when_output_empty(self):
        log = "\n".join(["step ok", "##[error]Process completed with exit code 1.", "FAILED tests"])
        checks = _summarize_check_runs(
            [
                {
                    "name": "ci",
                    "conclusion": "failure",
                    "output": {},
                    "external_id": "999",
                    "app": {"slug": "github-actions"},
                }
            ],
            job_log_fetcher=lambda _job: log,
        )
        self.assertIn("log_excerpt", checks[0])
        self.assertTrue(any("##[error]" in line for line in checks[0]["log_excerpt"]))

    def test_extract_fail_lines_from_log(self):
        log = "ok\n" * 40 + "##[error]boom\nTraceback"
        lines = _extract_fail_lines_from_log(log)
        self.assertLessEqual(len(lines), 16)
        self.assertTrue(any("##[error]" in ln for ln in lines))

    def test_assemble_packet_facts_and_closes(self):
        packet = assemble_packet(
            repo="octo/repo",
            pr_number=42,
            graphql=FIXTURE_GRAPHQL,
            head_sha="abc123",
            behind_by=2,
            checks=[{"name": "ci", "conclusion": "success"}],
            probe_meta={"changed": True, "not_modified": False},
            max_bytes=DEFAULT_MAX_BYTES,
        )
        facts = packet["facts"]
        self.assertEqual(facts["base_branch"], "main")
        self.assertEqual(facts["head_sha"], "abc123")
        self.assertEqual(facts["behind_by"], 2)
        self.assertEqual(facts["mergeStateStatus"], "BEHIND")
        self.assertIn(1364, facts["closes_issues"])
        self.assertIn(100, facts["closes_issues"])
        self.assertEqual(len(packet["review_threads"]), 3)

    def test_size_cap_uses_canonical_serialization(self):
        huge_checks = [
            {
                "name": f"job-{i}",
                "conclusion": "failure",
                "output": {"text": "\n".join(f"line-{j}" for j in range(80))},
            }
            for i in range(40)
        ]
        packet = assemble_packet(
            repo="octo/repo",
            pr_number=1,
            graphql=FIXTURE_GRAPHQL,
            head_sha="sha",
            behind_by=0,
            checks=huge_checks,
            probe_meta={},
            max_bytes=800,
        )
        self.assertTrue(packet.get("truncated"))
        text = serialize_pr_packet(packet)
        self.assertLessEqual(len(text.encode("utf-8")), 800)
        self.assertEqual(packet["byte_size"], len(text.encode("utf-8")))

    def test_packet_probe_state_path_is_separate_from_babysit_watch(self):
        watch = probe_state_path("octo/repo", 7, root="/tmp")
        packet = packet_probe_state_path("octo/repo", 7, root="/tmp")
        self.assertNotEqual(watch, packet)
        self.assertIn("packet-probe", str(packet))

    def test_load_pr_graphql_paginates_review_threads(self):
        page_one = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "body": "",
                        "baseRefName": "main",
                        "headRefOid": "sha",
                        "labels": {"nodes": []},
                        "milestone": None,
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                            "nodes": [{"id": "t1", "isResolved": False, "isOutdated": False, "comments": {"nodes": []}}],
                        },
                    }
                }
            }
        }
        page_two = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "body": "",
                        "baseRefName": "main",
                        "headRefOid": "sha",
                        "labels": {"nodes": []},
                        "milestone": None,
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"id": "t2", "isResolved": False, "isOutdated": False, "comments": {"nodes": []}}],
                        },
                    }
                }
            }
        }
        client = MagicMock()
        client.api.side_effect = [page_one, page_two]
        loaded = _load_pr_graphql(client, "octo/repo", 1)
        self.assertEqual([t["id"] for t in loaded["reviewThreads"]], ["t1", "t2"])
        self.assertTrue(loaded["review_threads_complete"])


class PrPacketBuildTests(unittest.TestCase):
    @patch("plate_core.pr_packet.save_probe_state")
    @patch("plate_core.pr_packet.fetch_delta")
    @patch("plate_core.pr_packet.probe_pr")
    @patch("plate_core.pr_packet.resolve_repo", return_value="octo/repo")
    def test_build_passes_prior_since_and_saves_once_after_delta(
        self, _resolve, mock_probe, mock_delta, mock_save
    ):
        mock_probe.return_value = ProbeResult(
            changed=True,
            not_modified=False,
            pr=None,
            new_state=ProbeState(head_sha="abc123", last_checked_at="2026-01-02T00:00:00Z"),
        )
        mock_delta.return_value = {
            "issue_comments": [{"id": 1}],
            "review_comments": [],
            "reviews": [],
            "new_state": ProbeState(head_sha="abc123", last_issue_comment_id=1),
        }
        with tempfile.TemporaryDirectory() as tmp:
            prior_path = packet_probe_state_path("octo/repo", 99, root=tmp)
            save_probe_state(prior_path, ProbeState(last_checked_at="2026-01-01T00:00:00Z"))
            build_pr_packet(
                99,
                repo="octo/repo",
                probe_root=tmp,
                snapshot={"graphql": FIXTURE_GRAPHQL, "head_sha": "abc123", "behind_by": 0, "checks": []},
            )
        mock_delta.assert_called_once()
        _args, kwargs = mock_delta.call_args
        self.assertEqual(kwargs.get("since"), "2026-01-01T00:00:00Z")
        self.assertEqual(mock_save.call_count, 1)
        saved_state = mock_save.call_args[0][1]
        self.assertEqual(saved_state.last_issue_comment_id, 1)
        self.assertEqual(saved_state.last_checked_at, "2026-01-02T00:00:00Z")

    @patch("plate_core.pr_packet.fetch_delta")
    @patch("plate_core.pr_packet.probe_pr")
    @patch("plate_core.pr_packet.resolve_repo", return_value="octo/repo")
    def test_build_with_snapshot_records_ledger(self, _resolve, mock_probe, mock_delta):
        mock_probe.return_value = ProbeResult(
            changed=False,
            not_modified=True,
            pr=None,
            new_state=ProbeState(head_sha="abc123", etag='W/"x"'),
        )
        mock_delta.return_value = {
            "issue_comments": [],
            "review_comments": [],
            "reviews": [],
            "new_state": ProbeState(head_sha="abc123"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "ledger"
            result = build_pr_packet(
                99,
                repo="octo/repo",
                probe_root=tmp,
                snapshot={
                    "graphql": FIXTURE_GRAPHQL,
                    "head_sha": "abc123",
                    "behind_by": 0,
                    "checks": [],
                },
                record_ledger=True,
                turns=3,
                run_id="run-test",
                ledger_base_dir=ledger_dir,
            )
            self.assertIsInstance(result, PrPacketResult)
            self.assertTrue(result.not_modified)
            payload = json.loads(result.json_text)
            self.assertEqual(payload["pr_number"], 99)
            self.assertIsNotNone(result.ledger_entry)
            self.assertEqual(result.ledger_entry.get("turns"), 3)
            self.assertEqual(result.ledger_entry.get("handoff_packet_unit"), "bytes")
            self.assertEqual(
                result.ledger_entry.get("handoff_packet_size"),
                result.packet.get("byte_size"),
            )
            self.assertLessEqual(len(result.json_text.encode("utf-8")), DEFAULT_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
