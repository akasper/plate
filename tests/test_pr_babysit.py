import unittest
from unittest.mock import patch

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
        self.assertIn("owner", graphql_call[2])
        self.assertIn("repo", graphql_call[2])
        self.assertIn("number", graphql_call[2])

    def test_resolve_review_thread_uses_graphql_variables(self):
        fake = _FakeClient(
            responses={
                ("graphql", "POST"): {"data": {"resolveReviewThread": {"thread": {"id": "T1", "isResolved": True}}}}
            }
        )
        payload = resolve_review_thread(thread_id="T1", repo="akasper/plate", client=fake)
        self.assertTrue(payload["resolved"])
        graphql_call = fake.calls[0]
        self.assertIn("threadId", graphql_call[2])

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

    @patch("plate_core.pr_babysit.subprocess")
    @patch("plate_core.pr_babysit.tempfile.mkdtemp")
    @patch("plate_core.pr_babysit.shutil.rmtree")
    def test_babysit_pr_local_rebase_success(self, mock_rmtree, mock_mkdtemp, mock_subprocess):
        """Test local-rebase strategy performs rebase and push when out of sync."""
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
                        "reviewThreads": {"nodes": []},
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

        # mock worktree and git calls for success path
        mock_mkdtemp.return_value = "/tmp/fake-worktree"
        mock_subprocess.check_call.return_value = None  # fetch, worktree add, push
        mock_subprocess.run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        report = babysit_pr(
            repo=repo, pr_number=pr, act=True, branch_update_strategy="local-rebase", client=fake
        )

        self.assertTrue(report.out_of_sync)
        self.assertTrue(report.local_rebase_performed)
        self.assertTrue(report.local_rebase_success)
        self.assertFalse(report.local_rebase_conflict)
        self.assertIsNone(report.local_rebase_error)
        # no copilot trigger for local-rebase
        self.assertFalse(report.merge_trigger_posted)

    @patch("plate_core.pr_babysit.subprocess")
    @patch("plate_core.pr_babysit.tempfile.mkdtemp")
    @patch("plate_core.pr_babysit.shutil.rmtree")
    def test_babysit_pr_local_rebase_conflict(self, mock_rmtree, mock_mkdtemp, mock_subprocess):
        """Test local-rebase reports conflict without crashing."""
        repo = "akasper/plate"
        pr = 112
        graphql_endpoint = "graphql"

        pr_data_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "CONFLICTING",
                        "baseRefName": "main",
                        "headRefName": "feature-branch",
                        "reviewThreads": {"nodes": []},
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

        mock_mkdtemp.return_value = "/tmp/fake-worktree"
        # first run for rebase fails (conflict)
        mock_subprocess.run.return_value = type("R", (), {"returncode": 1, "stdout": "conflict!", "stderr": ""})()
        mock_subprocess.check_call.side_effect = [None, None]  # fetch, worktree add; rebase aborts inside

        report = babysit_pr(
            repo=repo, pr_number=pr, act=True, branch_update_strategy="local-rebase", client=fake
        )

        self.assertTrue(report.out_of_sync)
        self.assertTrue(report.local_rebase_performed)
        self.assertFalse(report.local_rebase_success)
        self.assertTrue(report.local_rebase_conflict)

    def test_long_running_command_protocol_in_guidance(self):
        """Regression test for #529: the long-running/background command protocol
        (record task_id, proactive poll, surface on kill/SIGTERM, cheap fallback)
        must be present in the shipped agent guidance (and thus in the plate persona
        and pr-babysit flows). This ensures agents automatically follow the expected
        behavior instead of ignoring killed background tasks or defaulting to expensive
        full re-runs.
        """
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        protocol = "Long-running command / background task protocol"
        self.assertIn(protocol, QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Immediately record the task_id", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("plan and invoke `get_command_or_subagent_output` (or the `monitor` tool) at intervals", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("treat the kill as data", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Immediately retrieve the final/partial output via the get/monitor tool", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Switch *immediately* to a cheap, targeted fallback", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("cheap, targeted fallback", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("default to cheap, CI-log-driven reproduction first", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("pr-babysit", QUIET_OPERATIONS_GUIDANCE)

    def test_full_pr_green_make_mergeable_loop_in_guidance(self):
        """Regression test for #528: the 'Full PR Green / Make Mergeable Loop'
        (systematic 'current failing gates' model, own the inspect-fix-push-reinspect
        cycle, comprehensive ownership instead of single-category fixes waiting for
        user diagnosis, report summary only after exhausting agent actions) must be
        present in shipped guidance (and pr-babysit skill / persona / AGENTS.md).
        This ensures agents treat "get PR green" as an agent-owned loop.
        """
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        loop = "Full PR Green / Make Mergeable Loop"
        self.assertIn(loop, QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("current failing gates", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("inspect-fix-push-reinspect cycle", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("comprehensively inspect *all* current failing gates", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Push all changes to the *existing* PR branch", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Repeat the inspect-fix-push-reinspect cycle until no more agent-actionable items remain", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("only human-judgment items remain", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("one-sentence summary for the human of what is left", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("pr-babysit", QUIET_OPERATIONS_GUIDANCE)

    def test_ci_diagnosis_first_protocol_in_guidance(self):
        """Regression test for #527: the 'CI Diagnosis First Protocol' (always start
        with cheap GitHub inspection via gh pr checks + gh run view on the *specific*
        failing job *before* any broad/expensive local verification like multi-hour
        pytest in worktrees; only then decide minimal targeted scope) must be present
        in shipped guidance (and pr-babysit skill / persona / AGENTS.md babysit examples).
        This prevents wasted runs and ensures diagnosis is based on current CI state.
        """
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        protocol = "CI Diagnosis First Protocol"
        self.assertIn(protocol, QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Always begin with cheap, precise GitHub-side diagnosis", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("gh pr checks <pr-number>", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("gh run list --branch <pr-head-branch> --limit 5", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("gh run view <run-id> --job <job-id> --log-failed", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("*before* launching any broad or long-running local command", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Only *after* the precise diagnosis", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("pr-babysit", QUIET_OPERATIONS_GUIDANCE)

    def test_get_pr_merge_gates_returns_expected_keys(self):
        """Regression test for #526: get_pr_merge_gates helper returns the expected keys (merge_state, out_of_sync, unresolved_review_threads, actionable_agent_threads, note)."""
        from plate_core.pr_babysit import get_pr_merge_gates
        repo = "akasper/plate"
        pr = 112
        pr_data_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "BEHIND",
                        "baseRefName": "main",
                        "headRefName": "feature-branch",
                        "reviewThreads": {"nodes": []},
                    }
                }
            }
        }
        fake = _FakeClient(
            responses={
                ("graphql", "POST"): pr_data_payload,
            }
        )
        result = get_pr_merge_gates(pr_number=pr, repo=repo, client=fake)
        self.assertIn("merge_state", result)
        self.assertIn("out_of_sync", result)
        self.assertIn("unresolved_review_threads", result)
        self.assertIn("actionable_agent_threads", result)
        self.assertIn("note", result)

    def test_long_running_background_task_protocol_in_guidance(self):
        """Regression test for #525: the long-running/background task protocol (record task_id, proactively schedule/polling with get_command_or_subagent_output or monitor at intervals rather than waiting for reminders, consider lightweight monitor helper) must be present in shipped guidance (and thus in the plate persona and pr-babysit flows)."""
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        protocol = "Long-running command / background task protocol"
        self.assertIn(protocol, QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Immediately record the task_id", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Schedule proactive polling", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("plan and invoke `get_command_or_subagent_output` (or the `monitor` tool) at intervals", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("lightweight \"monitor\" helper", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("do not wait for system reminders", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("pr-babysit", QUIET_OPERATIONS_GUIDANCE)


if __name__ == "__main__":
    unittest.main()
