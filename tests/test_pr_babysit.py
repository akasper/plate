import unittest

from plate_core.pr_babysit import (
    _default_agent_match,
    _extract_actionable_threads,
    _detect_base_branch_out_of_sync,
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

    def test_detect_base_branch_out_of_sync_behind(self):
        """Test detection when PR branch is behind base branch."""
        pr_data = {
            "mergeStateStatus": "BEHIND",
            "baseRefName": "main",
            "headRefName": "feature-branch"
        }
        result = _detect_base_branch_out_of_sync(pr_data)
        self.assertTrue(result["out_of_sync"])
        self.assertEqual(result["state"], "BEHIND")
        self.assertEqual(result["base_ref"], "main")
        self.assertEqual(result["head_ref"], "feature-branch")

    def test_detect_base_branch_out_of_sync_conflicting(self):
        """Test detection when PR has merge conflicts."""
        pr_data = {
            "mergeStateStatus": "CONFLICTING",
            "baseRefName": "main",
            "headRefName": "feature-branch"
        }
        result = _detect_base_branch_out_of_sync(pr_data)
        self.assertTrue(result["out_of_sync"])
        self.assertEqual(result["state"], "CONFLICTING")

    def test_detect_base_branch_out_of_sync_dirty(self):
        """Test detection when PR is dirty (needs rebase)."""
        pr_data = {
            "mergeStateStatus": "DIRTY",
            "baseRefName": "main",
            "headRefName": "feature-branch"
        }
        result = _detect_base_branch_out_of_sync(pr_data)
        self.assertTrue(result["out_of_sync"])
        self.assertEqual(result["state"], "DIRTY")

    def test_detect_base_branch_out_of_sync_clean(self):
        """Test no detection when PR is up to date."""
        pr_data = {
            "mergeStateStatus": "CLEAN",
            "baseRefName": "main",
            "headRefName": "feature-branch"
        }
        result = _detect_base_branch_out_of_sync(pr_data)
        self.assertFalse(result["out_of_sync"])
        self.assertEqual(result["state"], "CLEAN")

    def test_babysit_pr_detects_out_of_sync_and_posts_copilot_trigger(self):
        """Test that babysit_pr detects out-of-sync state and posts Copilot merge-request trigger."""
        repo = "akasper/plate"
        pr = 112
        graphql_endpoint = "graphql"

        # First GraphQL call returns PR data with BEHIND state
        pr_data_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "BEHIND",
                        "baseRefName": "main",
                        "headRefName": "feature-branch",
                        "reviewThreads": {
                            "nodes": []
                        }
                    }
                }
            }
        }

        fake = _FakeClient(
            responses={
                (graphql_endpoint, "POST"): pr_data_payload,
                (f"repos/{repo}/issues/{pr}/comments?per_page=100&sort=created&direction=desc", "GET"): [],
                (f"repos/{repo}/issues/{pr}/comments", "POST"): {"html_url": "https://example.com/merge-trigger"},
            }
        )

        report = babysit_pr(repo=repo, pr_number=pr, act=True, branch_update_strategy="copilot-request", client=fake)

        # Should detect out of sync state
        self.assertTrue(hasattr(report, "out_of_sync"))
        self.assertTrue(report.out_of_sync)
        self.assertEqual(report.merge_state, "BEHIND")

        # Should post merge trigger comment
        self.assertTrue(report.merge_trigger_posted)
        self.assertEqual(report.merge_trigger_url, "https://example.com/merge-trigger")

        # Verify the comment was posted
        post_calls = [c for c in fake.calls if c[1] == "POST" and "/comments" in c[0] and "graphql" not in c[0]]
        self.assertEqual(len(post_calls), 1)
        comment_body = post_calls[0][2]["body"]
        self.assertIn("@copilot", comment_body.lower())
        self.assertIn("merge", comment_body.lower())

    def test_babysit_pr_respects_branch_update_strategy_none(self):
        """Test that branch_update_strategy=none skips merge trigger."""
        repo = "akasper/plate"
        pr = 112
        graphql_endpoint = "graphql"

        pr_data_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "BEHIND",
                        "baseRefName": "main",
                        "headRefName": "feature-branch",
                        "reviewThreads": {
                            "nodes": []
                        }
                    }
                }
            }
        }

        fake = _FakeClient(
            responses={
                (graphql_endpoint, "POST"): pr_data_payload,
                (f"repos/{repo}/issues/{pr}/comments?per_page=100&sort=created&direction=desc", "GET"): [],
            }
        )

        report = babysit_pr(repo=repo, pr_number=pr, act=True, branch_update_strategy="none", client=fake)

        # Should still detect out of sync
        self.assertTrue(report.out_of_sync)

        # Should NOT post merge trigger
        self.assertFalse(report.merge_trigger_posted)

        # No POST calls to comments endpoint
        post_calls = [c for c in fake.calls if c[1] == "POST" and "/comments" in c[0] and "graphql" not in c[0]]
        self.assertEqual(len(post_calls), 0)


if __name__ == "__main__":
    unittest.main()
