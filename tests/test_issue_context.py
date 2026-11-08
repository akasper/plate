"""Tests for typed issue-context resolution (#1449)."""

from __future__ import annotations

import unittest

from plate_core.github_client import GhApiError
from plate_core.issue_context import (
    IssueContextStatus,
    detect_unparsed_closing_candidates,
    fetch_issue_labels_for_ref,
    parse_closing_issue_refs,
    resolve_issue_context,
    sidebar_linked_issue_refs,
)
from plate_core.issue_context import IssueRef


class IssueContextParseTests(unittest.TestCase):
    def test_cross_repo_url_preserves_identity(self):
        body = "Closes https://github.com/other/remote/issues/99\n"
        refs = parse_closing_issue_refs(body, default_repo="akasper/plate")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].repo_full, "other/remote")
        self.assertEqual(refs[0].number, 99)

    def test_inline_code_closing_unavailable(self):
        body = "Summary\n\n`Closes #42` in backticks\n"
        self.assertTrue(detect_unparsed_closing_candidates(body))
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body=body,
            client=_NoGh(),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.UNAVAILABLE)

    def test_quoted_hash_not_used_for_routing(self):
        body = "Closes #10\n\nMention `#11` in prose only.\n"
        refs = parse_closing_issue_refs(body, default_repo="o/r")
        nums = {r.number for r in refs}
        self.assertEqual(nums, {10})

    def test_not_required_without_strict_type(self):
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["no-issue"],
            body="Closes #1",
            client=_NoGh(),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.NOT_REQUIRED)


class IssueContextFetchTests(unittest.TestCase):
    def test_missing_labels_field_fails_closed(self):
        ref = IssueRef(owner="o", repo="r", number=1, source="closing_body")
        labels, err = fetch_issue_labels_for_ref(ref, client=_GhIssues({1: {"title": "x"}}))  # type: ignore[arg-type]
        self.assertEqual(labels, [])
        self.assertIn("labels", err or "")

    def test_empty_labels_list_fails_closed(self):
        ref = IssueRef(owner="o", repo="r", number=2, source="closing_body")
        labels, err = fetch_issue_labels_for_ref(ref, client=_GhIssues({2: {"labels": []}}))  # type: ignore[arg-type]
        self.assertIn("no labels", (err or "").lower())

    def test_404_vs_network_error(self):
        ref = IssueRef(owner="o", repo="r", number=3, source="closing_body")

        labels, err = fetch_issue_labels_for_ref(ref, client=_Gh404())  # type: ignore[arg-type]
        self.assertIn("not found", (err or "").lower())

        labels2, err2 = fetch_issue_labels_for_ref(ref, client=_GhRateLimit())  # type: ignore[arg-type]
        self.assertIn("Could not load", err2 or "")


class IssueContextSidebarTests(unittest.TestCase):
    def test_sidebar_replay_adds_ref(self):
        refs, err = sidebar_linked_issue_refs(
            "o/r",
            5,
            client=_GhSidebar([7]),  # type: ignore[arg-type]
        )
        self.assertIsNone(err)
        self.assertEqual([r.number for r in refs or []], [7])


class IssueContextResolveTests(unittest.TestCase):
    def test_absent_closing_keyword_body(self):
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body="Summary only\n",
            client=_NoGh(),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.ABSENT)

    def test_ok_merges_issue_labels(self):
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body="Closes #42\n",
            client=_GhIssues(
                {
                    42: {"labels": [{"name": "Minor"}, {"name": "Feature"}]},
                }
            ),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.OK)
        self.assertIn("Minor", result.labels)


class _NoGh:
    def api(self, *_a, **_k):
        raise AssertionError("unexpected API call")


class _GhIssues:
    def __init__(self, issues: dict[int, dict]) -> None:
        self._issues = issues

    def api(self, endpoint: str, **_kwargs):
        if endpoint.startswith("repos/") and "/issues/" in endpoint:
            num = int(endpoint.rsplit("/", 1)[-1])
            if num in self._issues:
                return self._issues[num]
            raise GhApiError("HTTP 404 Not Found")
        raise AssertionError(endpoint)


class _Gh404:
    def api(self, _endpoint: str, **_kwargs):
        raise GhApiError("HTTP 404 Not Found")


class _GhRateLimit:
    def api(self, _endpoint: str, **_kwargs):
        raise GhApiError("rate limit exceeded")


class _GhSidebar:
    def __init__(self, nums: list[int]) -> None:
        self._nums = nums

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None, **_kwargs):
        if endpoint == "graphql" and method == "POST":
            nodes = [
                {
                    "__typename": "ConnectedEvent",
                    "subject": {"__typename": "Issue", "id": f"I_{n}", "number": n},
                }
                for n in self._nums
            ]
            return {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "timelineItems": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": nodes,
                            }
                        }
                    }
                }
            }
        raise AssertionError(endpoint)


if __name__ == "__main__":
    unittest.main()
