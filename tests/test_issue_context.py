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
    strip_blockquotes_for_scan,
)
from plate_core.issue_context import IssueRef


class IssueContextParseTests(unittest.TestCase):
    def test_cross_repo_url_preserves_identity(self):
        body = "Closes https://github.com/other/remote/issues/99\n"
        refs = parse_closing_issue_refs(body, default_repo="akasper/plate")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].repo_full, "other/remote")

    def test_blockquote_closes_ignored(self):
        body = "> Closes #42\n\nCloses #10\n"
        self.assertNotIn("42", strip_blockquotes_for_scan(body))
        refs = parse_closing_issue_refs(body, default_repo="o/r")
        self.assertEqual({r.number for r in refs}, {10})

    def test_inline_code_closing_unavailable_when_no_other_ref(self):
        body = "Summary\n\n`Closes #42` in backticks\n"
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body=body,
            client=_NoGh(),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.UNAVAILABLE)

    def test_inline_code_ok_when_sidebar_supplies_ref(self):
        body = "`Closes #42`\n"
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body=body,
            pr_number=1,
            client=_GhSidebarAndIssues(
                sidebar_num=10,
                sidebar_repo="other/remote",
                issues={10: {"labels": [{"name": "Minor"}]}},
            ),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.OK)
        self.assertEqual(result.refs[0].repo_full, "other/remote")

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

    def test_empty_labels_list_is_verified_empty(self):
        ref = IssueRef(owner="o", repo="r", number=2, source="closing_body")
        labels, err = fetch_issue_labels_for_ref(ref, client=_GhIssues({2: {"labels": []}}))  # type: ignore[arg-type]
        self.assertEqual(labels, [])
        self.assertIsNone(err)

    def test_404_vs_network_error(self):
        ref = IssueRef(owner="o", repo="r", number=3, source="closing_body")
        _, err = fetch_issue_labels_for_ref(ref, client=_Gh404())  # type: ignore[arg-type]
        self.assertIn("not found", (err or "").lower())
        _, err2 = fetch_issue_labels_for_ref(ref, client=_GhRateLimit())  # type: ignore[arg-type]
        self.assertIn("Could not load", err2 or "")


class IssueContextSidebarTests(unittest.TestCase):
    def test_sidebar_cross_repo_identity(self):
        refs, err = sidebar_linked_issue_refs(
            "akasper/plate",
            5,
            client=_GhSidebarRemote(7, "other/remote"),  # type: ignore[arg-type]
        )
        self.assertIsNone(err)
        assert refs
        self.assertEqual(refs[0].repo_full, "other/remote")
        self.assertEqual(refs[0].number, 7)

    def test_graphql_errors_fail_closed(self):
        refs, err = sidebar_linked_issue_refs("o/r", 1, client=_GhGraphQLErrors())  # type: ignore[arg-type]
        self.assertIsNone(refs)
        self.assertIn("GraphQL", err or "")

    def test_stalled_pagination_fails_closed(self):
        refs, err = sidebar_linked_issue_refs("o/r", 1, client=_GhStallPagination())  # type: ignore[arg-type]
        self.assertIsNone(refs)
        self.assertIn("pagination", (err or "").lower())


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
                {42: {"labels": [{"name": "Minor"}, {"name": "Feature"}]}},
            ),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.OK)
        self.assertIn("Minor", result.labels)

    def test_ok_with_empty_issue_labels(self):
        result = resolve_issue_context(
            pr_repo="o/r",
            pr_labels=["Feature"],
            body="Closes #1\n",
            client=_GhIssues({1: {"labels": []}}),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, IssueContextStatus.OK)
        self.assertEqual(result.labels, [])


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


def _sidebar_payload(nums: list[tuple[int, str]], *, page: dict) -> dict:
    nodes = [
        {
            "__typename": "ConnectedEvent",
            "subject": {
                "__typename": "Issue",
                "id": f"I_{n}",
                "number": n,
                "repository": {"nameWithOwner": repo},
            },
        }
        for n, repo in nums
    ]
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "timelineItems": {
                        "pageInfo": page,
                        "nodes": nodes,
                    }
                }
            }
        }
    }


class _GhSidebarRemote:
    def __init__(self, num: int, repo: str) -> None:
        self._num = num
        self._repo = repo

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None, **_kwargs):
        if endpoint == "graphql" and method == "POST":
            return _sidebar_payload(
                [(self._num, self._repo)],
                page={"hasNextPage": False, "endCursor": None},
            )
        raise AssertionError(endpoint)


class _GhSidebarAndIssues(_GhIssues):
    def __init__(self, *, sidebar_num: int, sidebar_repo: str, issues: dict[int, dict]) -> None:
        super().__init__(issues)
        self._remote = _GhSidebarRemote(sidebar_num, sidebar_repo)

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None, **_kwargs):
        if endpoint == "graphql" and method == "POST":
            return self._remote.api(endpoint, method=method, fields=fields, **_kwargs)
        return super().api(endpoint, **_kwargs)


class _GhGraphQLErrors:
    def api(self, endpoint: str, method: str = "GET", **_kwargs):
        if endpoint == "graphql" and method == "POST":
            return {"errors": [{"message": "FORBIDDEN"}]}
        raise AssertionError(endpoint)


class _GhStallPagination:
    def api(self, endpoint: str, method: str = "GET", **_kwargs):
        if endpoint == "graphql" and method == "POST":
            return _sidebar_payload(
                [(1, "o/r")],
                page={"hasNextPage": True, "endCursor": "CURSOR_A"},
            )
        raise AssertionError(endpoint)


if __name__ == "__main__":
    unittest.main()
