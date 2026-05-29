import unittest

from plate_core.pr_babysit import (
    _default_agent_match,
    _extract_actionable_threads,
    babysit_pr,
    resolve_review_thread,
)


class _FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
        self.calls.append((endpoint, method, fields))
        key = (endpoint, method)
        return self.responses.get(key, self.responses.get(endpoint, {}))


class PrBabysitTests(unittest.TestCase):
    def test_default_agent_match(self):
        self.assertTrue(_default_agent_match("devin-ai-integration[bot]"))
        self.assertTrue(_default_agent_match("OpenHands-Agent"))
        self.assertFalse(_default_agent_match("octocat"))

    def test_extract_actionable_threads_filters_resolved_and_outdated(self):
        threads = [
            {
                "id": "T1",
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {"databaseId": 1, "body": "please change this", "url": "u1", "author": {"login": "devin-ai"}}
                    ]
                },
            },
            {
                "id": "T2",
                "isResolved": True,
                "isOutdated": False,
                "comments": {"nodes": [{"databaseId": 2, "body": "done", "url": "u2", "author": {"login": "devin-ai"}}]},
            },
            {
                "id": "T3",
                "isResolved": False,
                "isOutdated": True,
                "comments": {"nodes": [{"databaseId": 3, "body": "stale", "url": "u3", "author": {"login": "devin-ai"}}]},
            },
        ]
        actionable = _extract_actionable_threads(threads, agent_logins=None)
        self.assertEqual(len(actionable), 1)
        self.assertEqual(actionable[0]["thread_id"], "T1")

    def test_babysit_pr_posts_trigger_comment_when_act_true(self):
        repo = "akasper/plate"
        pr = 112
        graphql_endpoint = "graphql"
        threads_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "T1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 101,
                                                "body": "fix this",
                                                "url": "https://example.com/t1",
                                                "author": {"login": "devin-ai"},
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        }
        fake = _FakeClient(
            responses={
                (f"repos/{repo}/issues/{pr}/comments?per_page=100&sort=created&direction=desc", "GET"): [],
                (graphql_endpoint, "POST"): threads_payload,
                (f"repos/{repo}/issues/{pr}/comments", "POST"): {"html_url": "https://example.com/posted"},
            }
        )
        report = babysit_pr(repo=repo, pr_number=pr, act=True, client=fake)
        self.assertEqual(report.actionable_threads, 1)
        self.assertTrue(report.trigger_comment_posted)
        self.assertEqual(report.trigger_comment_url, "https://example.com/posted")
        graphql_call = fake.calls[0]
        self.assertEqual(graphql_call[0], "graphql")
        self.assertEqual(graphql_call[1], "POST")
        self.assertIn("variables[owner]", graphql_call[2])
        self.assertIn("variables[repo]", graphql_call[2])
        self.assertIn("variables[number]", graphql_call[2])

    def test_resolve_review_thread_uses_graphql_variables(self):
        fake = _FakeClient(
            responses={
                ("graphql", "POST"): {"data": {"resolveReviewThread": {"thread": {"id": "T1", "isResolved": True}}}}
            }
        )
        payload = resolve_review_thread(thread_id="T1", repo="akasper/plate", client=fake)
        self.assertTrue(payload["resolved"])
        graphql_call = fake.calls[0]
        self.assertIn("variables[threadId]", graphql_call[2])

    def test_babysit_uses_desc_sort_on_comments_api_to_find_recent_markers(self):
        """Regression test for the pagination/sort bug reported by Devin in thread PRRT_kwDOSn5ouc6Fic4A.

        Without &sort=created&direction=desc, the default ascending order means recent babysit
        markers (posted after >100 comments on the PR) are not in the first per_page=100 page.
        This test asserts the query string construction includes the reverse sort so the check
        for existing marker sees recent comments first. Uses act=True + actionable thread to
        exercise the _has_existing_babysit_comment path (the call is conditional on posting logic).
        """
        repo = "akasper/plate"
        pr = 120
        graphql_endpoint = "graphql"
        threads_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "TDEVIN",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 999,
                                                "body": "fix the sort",
                                                "url": "https://example.com/tdevin",
                                                "author": {"login": "devin-ai-integration[bot]"},
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        }
        fake = _FakeClient(
            responses={
                (graphql_endpoint, "POST"): threads_payload,
                # Note: no comments GET key provided; will use default {} -> no marker -> would post
                (f"repos/{repo}/issues/{pr}/comments", "POST"): {"html_url": "https://example.com/trigger"},
            }
        )
        report = babysit_pr(repo=repo, pr_number=pr, act=True, client=fake)
        self.assertEqual(report.actionable_threads, 1)
        comments_calls = [c for c in fake.calls if "/comments" in c[0] and "issues" in c[0] and "POST" not in str(c)]
        self.assertEqual(len(comments_calls), 1, "should query comments GET for existing marker check")
        endpoint = comments_calls[0][0]
        self.assertIn("per_page=100", endpoint)
        self.assertIn("sort=created", endpoint)
        self.assertIn("direction=desc", endpoint)
        self.assertTrue(
            "sort=created&direction=desc" in endpoint,
            f"endpoint must include reverse sort for recent marker detection: {endpoint}"
        )


if __name__ == "__main__":
    unittest.main()
