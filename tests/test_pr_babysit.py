import unittest
from unittest.mock import patch

from plate_core.pr_babysit import (
    _default_agent_match,
    _extract_actionable_threads,
    _extract_outdated_unresolved_threads,
    _detect_base_branch_out_of_sync,
    babysit_pr,
    extract_suggestion_blocks,
    resolve_pr_review_scope,
    resolve_review_thread,
)


class _FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def api(self, endpoint: str, method: str = "GET", fields: dict | None = None):
        self.calls.append((endpoint, method, fields))
        # Dispatch GraphQL by mutation/query so resolve and load can share POST endpoint (#605)
        if endpoint == "graphql" and method == "POST" and fields:
            query = fields.get("query") or ""
            if "resolveReviewThread" in query:
                key = ("graphql", "POST", "resolve")
                if key in self.responses:
                    return self.responses[key]
                # default successful resolve
                tid = fields.get("threadId", "T?")
                return {"data": {"resolveReviewThread": {"thread": {"id": tid, "isResolved": True}}}}
            if "pullRequest" in query or "reviewThreads" in query:
                key = ("graphql", "POST", "load")
                if key in self.responses:
                    return self.responses[key]
        key = (endpoint, method)
        return self.responses.get(key, self.responses.get(endpoint, {}))


class PrBabysitTests(unittest.TestCase):
    def test_default_agent_match(self):
        self.assertTrue(_default_agent_match("devin-ai-integration[bot]"))
        self.assertTrue(_default_agent_match("OpenHands-Agent"))
        self.assertTrue(_default_agent_match("copilot-pull-request-reviewer"))
        self.assertTrue(_default_agent_match("github-copilot[bot]"))
        self.assertFalse(_default_agent_match("octocat"))

    def test_extract_suggestion_blocks_496(self):
        body = "Please rename this:\n```suggestion\nnew_name = 1\n```\nThanks"
        blocks = extract_suggestion_blocks(body)
        self.assertEqual(len(blocks), 1)
        self.assertIn("new_name = 1", blocks[0])
        self.assertEqual(extract_suggestion_blocks("no fence"), [])

    def test_pr_review_scope_filters_authors_496(self):
        threads = [
            {
                "id": "T_copilot",
                "isResolved": False,
                "isOutdated": False,
                "path": "src/plate_core/pr_babysit.py",
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 1,
                            "body": "```suggestion\nx = 1\n```",
                            "url": "u1",
                            "author": {"login": "copilot-pull-request-reviewer"},
                        }
                    ]
                },
            },
            {
                "id": "T_human",
                "isResolved": False,
                "isOutdated": False,
                "path": "src/ok.py",
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 2,
                            "body": "please clarify",
                            "url": "u2",
                            "author": {"login": "octocat"},
                        }
                    ]
                },
            },
        ]
        all_scope = _extract_actionable_threads(threads, None, scope="all")
        self.assertEqual(len(all_scope), 2)
        bot_only = _extract_actionable_threads(threads, None, scope="bot-only")
        self.assertEqual(len(bot_only), 1)
        self.assertEqual(bot_only[0]["thread_id"], "T_copilot")
        self.assertTrue(bot_only[0]["has_suggestion"])
        self.assertTrue(bot_only[0]["prefer_apply_suggestion"])
        human_only = _extract_actionable_threads(threads, None, scope="human-only")
        self.assertEqual(len(human_only), 1)
        self.assertEqual(human_only[0]["thread_id"], "T_human")
        # explicit allowlist overrides scope
        allow = _extract_actionable_threads(threads, "octocat", scope="bot-only")
        self.assertEqual(len(allow), 1)
        self.assertEqual(allow[0]["author"], "octocat")

    def test_high_risk_path_blocks_prefer_apply_496(self):
        threads = [
            {
                "id": "T_agents",
                "isResolved": False,
                "isOutdated": False,
                "path": "AGENTS.md",
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 9,
                            "body": "```suggestion\n# wipe\n```",
                            "url": "u",
                            "author": {"login": "copilot-pull-request-reviewer"},
                        }
                    ]
                },
            }
        ]
        items = _extract_actionable_threads(threads, None, scope="all")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["high_risk_path"])
        self.assertFalse(items[0]["prefer_apply_suggestion"])

    def test_babysit_pr_scope_all_includes_copilot_496(self):
        repo = "akasper/plate"
        pr = 496
        threads_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "CLEAN",
                        "baseRefName": "main",
                        "headRefName": "feature/496",
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "PRRT_copilot",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "path": "src/plate_core/cli.py",
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 42,
                                                "body": "nit:\n```suggestion\nprint('ok')\n```",
                                                "url": "https://example.com/c",
                                                "author": {"login": "copilot-pull-request-reviewer"},
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                }
            }
        }
        fake = _FakeClient(responses={("graphql", "POST", "load"): threads_payload})
        report = babysit_pr(repo=repo, pr_number=pr, act=False, pr_review_scope="all", client=fake)
        self.assertEqual(report.pr_review_scope, "all")
        self.assertEqual(report.actionable_threads, 1)
        self.assertEqual(report.threads_with_suggestions, 1)
        # Pre-#496 bot-only without copilot patterns would have been 0; patterns now include copilot
        report_bot = babysit_pr(repo=repo, pr_number=pr, act=False, pr_review_scope="bot-only", client=fake)
        self.assertEqual(report_bot.actionable_threads, 1)

    def test_resolve_pr_review_scope_validation_496(self):
        self.assertEqual(resolve_pr_review_scope("ALL"), "all")
        self.assertEqual(resolve_pr_review_scope("bot_only"), "bot-only")
        with self.assertRaises(ValueError):
            resolve_pr_review_scope("friends-only")

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

    def test_extract_outdated_unresolved_threads_for_605(self):
        threads = [
            {
                "id": "T_fresh",
                "isResolved": False,
                "isOutdated": False,
                "comments": {"nodes": [{"databaseId": 1, "body": "open", "url": "u1", "author": {"login": "devin-ai"}}]},
            },
            {
                "id": "T_outdated",
                "isResolved": False,
                "isOutdated": True,
                "comments": {"nodes": [{"databaseId": 2, "body": "fixed", "url": "u2", "author": {"login": "copilot"}}]},
            },
            {
                "id": "T_resolved_outdated",
                "isResolved": True,
                "isOutdated": True,
                "comments": {"nodes": [{"databaseId": 3, "body": "done", "url": "u3", "author": {"login": "devin-ai"}}]},
            },
        ]
        candidates = _extract_outdated_unresolved_threads(threads)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["thread_id"], "T_outdated")

    def test_babysit_pr_act_auto_resolves_outdated_unresolved_threads_605(self):
        """#605: act=True must resolve outdated+unresolved threads (post-fix state)."""
        repo = "akasper/plate"
        pr = 601
        threads_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "CLEAN",
                        "baseRefName": "main",
                        "headRefName": "feature/x",
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "PRRT_outdated_1",
                                    "isResolved": False,
                                    "isOutdated": True,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 201,
                                                "body": "please rename",
                                                "url": "https://example.com/t1",
                                                "author": {"login": "akasper"},
                                            }
                                        ]
                                    },
                                },
                                {
                                    "id": "PRRT_outdated_2",
                                    "isResolved": False,
                                    "isOutdated": True,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 202,
                                                "body": "nit",
                                                "url": "https://example.com/t2",
                                                "author": {"login": "copilot-pull-request-reviewer"},
                                            }
                                        ]
                                    },
                                },
                                {
                                    "id": "PRRT_still_actionable",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 203,
                                                "body": "still open",
                                                "url": "https://example.com/t3",
                                                "author": {"login": "devin-ai"},
                                            }
                                        ]
                                    },
                                },
                            ]
                        },
                    }
                }
            }
        }
        fake = _FakeClient(
            responses={
                ("graphql", "POST", "load"): threads_payload,
                (f"repos/{repo}/issues/{pr}/comments?per_page=100&sort=created&direction=desc", "GET"): [],
                (f"repos/{repo}/issues/{pr}/comments", "POST"): {"html_url": "https://example.com/posted"},
            }
        )
        report = babysit_pr(repo=repo, pr_number=pr, act=True, client=fake)
        self.assertEqual(report.actionable_threads, 1)
        self.assertEqual(report.auto_resolved_threads, 2)
        self.assertEqual(
            set(report.auto_resolved_thread_ids or []),
            {"PRRT_outdated_1", "PRRT_outdated_2"},
        )
        resolve_calls = [
            c for c in fake.calls
            if c[0] == "graphql" and c[1] == "POST" and c[2] and "resolveReviewThread" in (c[2].get("query") or "")
        ]
        self.assertEqual(len(resolve_calls), 2)
        resolved_ids = {c[2]["threadId"] for c in resolve_calls}
        self.assertEqual(resolved_ids, {"PRRT_outdated_1", "PRRT_outdated_2"})

    def test_babysit_pr_without_act_does_not_auto_resolve_605(self):
        repo = "akasper/plate"
        pr = 602
        threads_payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "mergeStateStatus": "CLEAN",
                        "baseRefName": "main",
                        "headRefName": "feature/y",
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "PRRT_o",
                                    "isResolved": False,
                                    "isOutdated": True,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "databaseId": 1,
                                                "body": "stale",
                                                "url": "u",
                                                "author": {"login": "devin-ai"},
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                }
            }
        }
        fake = _FakeClient(responses={("graphql", "POST", "load"): threads_payload})
        report = babysit_pr(repo=repo, pr_number=pr, act=False, client=fake)
        self.assertEqual(report.auto_resolved_threads, 0)
        resolve_calls = [
            c for c in fake.calls
            if c[0] == "graphql" and c[1] == "POST" and c[2] and "resolveReviewThread" in (c[2].get("query") or "")
        ]
        self.assertEqual(len(resolve_calls), 0)

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
        self.assertIn("Push all changes to the *existing* PR branch", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("only human-judgment items remain", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("one-sentence summary for the human of what is left", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("pr-babysit", QUIET_OPERATIONS_GUIDANCE)
        # NOTE: we assert key phrases/section headers (not full verbatim multi-paragraph strings)
        # to prevent guidance churn and respect any persona size limits (#569 architecture relief).
        # See agent_guidance.py "Guidance architecture for persona byte limits..." comment.

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
                        },
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
        self.assertEqual(result["merge_state"], "BEHIND")
        self.assertTrue(result["out_of_sync"])
        self.assertEqual(result["unresolved_review_threads"], 1)
        self.assertEqual(result["actionable_agent_threads"], 1)
        self.assertIn("comprehensively", result["note"])
        self.assertIn("full gates", result["note"])

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

    def test_default_to_pr_babysit_skill_in_pr_babysit_instructions(self):
        """Regression test for #524: instructions must direct agents to default to the dedicated pr-babysit skill/MCP rather than hand-rolling raw git/gh for babysit/get-green/etc. instructions."""
        import plate_core.pr_babysit as mod
        doc = getattr(mod, "__doc__", "") or ""
        self.assertIn("must default to it (rather than hand-rolling git/gh commands)", doc)
        self.assertIn("addresses #524", doc)

        # Anchor in persona
        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("start with pr-babysit skill", persona)
        self.assertIn("not hand-rolling", persona)

    def test_verification_strategy_in_guidance(self):
        """Regression test for #523: verification strategy (narrow/targeted first with check-work skill, warn before long runs >5-10min, cross-ref to CI Diagnosis/long-running) must be present in shipped guidance and persona."""
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        self.assertIn("Verification Strategy (local test runs, reproduction, and check-work)", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("use the `check-work` skill", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("warn the user before starting", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn(">5-10 minutes", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("targeted command possible", QUIET_OPERATIONS_GUIDANCE)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("use check-work or targeted pytest", persona)
        self.assertIn("warn before long runs (see guidance)", persona)

    def test_gaps_in_docs_for_qanda_and_pr_health_fixed_in_guidance(self):
        """Regression test for #521: guidance, persona, and AGENTS must explicitly require native TUI (ask_user_question) for PLATE Q&A and integrated full PR health/babysit follow-through without repeated corrections."""
        from plate_core.agent_guidance import QANDA_CURIOSITY_GUIDANCE
        self.assertIn("Mandatory use of native TUI forms for Q&A in PLATE contexts", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("Enforcement of Q&A option follow-through", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("ask_user_question (or host native TUI)", QANDA_CURIOSITY_GUIDANCE)
        # Key-phrase asserts only (see guidance architecture note + #569 persona relief).

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("default to ask_user_question (native TUI); if option promises review/babysit", persona)
        self.assertIn("Follow guidance.", persona)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("consistently default to native TUI (ask_user_question arrow-key forms) and enforce full follow-through on answers", agents)

    def test_human_review_required_before_merge_for_certain_prs(self):
        """Regression test for #549: AGENTS.md must explicitly require human review/approval before merge for Bug/Feature/Documentation PRs (and at least one review for Epics/Releases), separate from feedback-resolution for agent threads."""
        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("do not self-merge", agents)
        self.assertIn("Epics and Releases require at least one review as well", agents)
        self.assertIn("This gate is *not* a substitute for the separate human review/approval requirement", agents)

    def test_resolve_review_threads_after_feedback_for_check(self):
        """Regression test for #520: AGENTS.md and pr_babysit instructions must require explicitly resolving review threads (via resolveReviewThread) after addressing feedback to clear the feedback-resolution check."""
        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("resolve addressed threads via `plate_resolve_review_thread`", agents)
        self.assertIn("encapsulated helper", agents)

        import plate_core.pr_babysit as mod
        doc = getattr(mod, "__doc__", "") or ""
        self.assertIn("explicitly resolve the corresponding review threads", doc)

    def test_complete_babysit_make_green_from_single_high_level_prompt(self):
        """Regression test for #519: guidance and AGENTS must describe a complete 'turn PR green' / full babysit flow from a *single high-level prompt* (not category-by-category), where the agent handles all agent-actionable gates (conflicts, labels, threads, tests) comprehensively using the skill + helpers, reporting summary only at end."""
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        self.assertIn("single high-level instruction", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("atomic \"complete babysit / turn green\" flow", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("one comprehensive pass (conflicts, labels, threads, tests, etc.)", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("from a single high-level prompt instead of sequential single-category fixes", QUIET_OPERATIONS_GUIDANCE)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("From a *single high-level prompt* (\"get this PR green\", \"make mergeable\", \"address all feedback\")", agents)
        self.assertIn("handle *all* agent-actionable categories (base sync/conflicts, labels, review threads, tests, etc.) in one or minimal comprehensive passes", agents)
        self.assertIn("(Addresses #519, #528, #526.)", agents)

    def test_agent_consistently_defaults_to_native_tui_for_qanda_518(self):
        """Regression test for #518: guidance, persona, and AGENTS must require agents to *consistently default to or use Grok Build native TUI interactive configurator (arrow-key forms)* for Q&A (without user reminder; with detection/fallback note)."""
        from plate_core.agent_guidance import QANDA_CURIOSITY_GUIDANCE
        self.assertIn("consistently default to or use", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("Grok Build native TUI interactive configurator (arrow-key forms)", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("detection/fallback", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("do not require user reminders", QANDA_CURIOSITY_GUIDANCE)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("default to ask_user_question (native TUI); if option promises review/babysit", persona)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("consistently default to native TUI (ask_user_question arrow-key forms) and enforce full follow-through on answers", agents)
        self.assertIn("(Addresses #503, #518, #517, #521 and closes the post-0.6.1 Q&A/babysit stub cluster under #580/#569 polish.)", agents)

    def test_qanda_follow_through_enforced_in_this_turn_517(self):
        """Regression test for #517: guidance and AGENTS enforce that interactive Q&A options (ask_user_question) only offer actions whose full follow-through (artifacts, execution) will complete in this turn; no advance until done."""
        from plate_core.agent_guidance import QANDA_CURIOSITY_GUIDANCE
        self.assertIn("Offer *only* options/actions in ask_user_question whose full follow-through", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("will be completed in this turn before any further progress or new Q&A", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("do not declare done or offer next until prior chosen option is fully executed", QANDA_CURIOSITY_GUIDANCE)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("Offer only options whose full execution+artifacts complete in-turn before further Q&A/progress", agents)

    def test_review_thread_handling_encapsulated_516(self):
        """Regression test for #516: pr_babysit skill + MCP + guidance + AGENTS + persona require use of encapsulated high-level helpers (get_actionable_review_threads / plate_get_actionable_review_threads + resolve_review_thread / plate_resolve...) for review threads; pagination, DBID, ANSI, mutation handled internally. Forbid hand-rolling GraphQL/jq/mktemp/sed."""
        import plate_core.pr_babysit as pbmod
        doc = getattr(pbmod, "__doc__", "") or ""
        self.assertIn("fully encapsulated in the high-level helpers", doc)
        self.assertIn("**must not** manually construct raw `gh api graphql`, jq filters", doc)
        self.assertIn("get_actionable_review_threads", doc)
        self.assertIn("(addresses #516)", doc)

        # Public helper exists and is importable
        self.assertTrue(hasattr(pbmod, "get_actionable_review_threads"))

        with open("src/plate_core/agent_guidance.py", encoding="utf-8") as f:
            guidance = f.read()
        self.assertIn("encapsulated helpers (get_actionable_review_threads", guidance)
        self.assertIn("Do not hand-roll raw GraphQL, jq, mktemp, sed/NO_COLOR", guidance)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("use plate_pr_babysit + plate_get_actionable_review_threads + plate_resolve_review_thread (encapsulated", agents)
        self.assertIn("Do not hand-roll GraphQL/jq/mktemp/sed", agents)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("Use encapsulated review helpers (no raw GraphQL/jq)", persona)

        import plate_core.pr_babysit as pbmod
        doc = getattr(pbmod, "__doc__", "") or ""
        self.assertIn("(addresses #516)", doc)

    def test_todo_write_required_for_complex_multi_step_515(self):
        """Regression test for #515: persona, agent_guidance, and AGENTS must require `todo_write` (mark completed immediately, never batch) for all 3+ step PLATE work (babysit sessions, Q&A refinement, full PR green, ceremonies)."""
        from plate_core.agent_guidance import TASK_MANAGEMENT_GUIDANCE
        self.assertIn("Task Management for Complex Multi-Step Work", TASK_MANAGEMENT_GUIDANCE)
        self.assertIn("**immediately** use the `todo_write` tool", TASK_MANAGEMENT_GUIDANCE)
        self.assertIn("Mark items completed as soon as the atomic step is done", TASK_MANAGEMENT_GUIDANCE)
        self.assertIn("babysit/\"get PR green\"", TASK_MANAGEMENT_GUIDANCE)
        self.assertIn("interactive Q&A or contemplation/refinement rounds", TASK_MANAGEMENT_GUIDANCE)
        self.assertIn("(Addresses #515.)", TASK_MANAGEMENT_GUIDANCE)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("start with todo_write; mark done immediately (no batch)", persona)
        self.assertIn("(Addresses #515.)", persona)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("## Task Management (for agents)", agents)
        self.assertIn("**must** use the `todo_write` tool (or host equivalent) for any complex multi-step PLATE work with 3+ steps", agents)
        self.assertIn("Mark each item `completed` **immediately** when that step finishes. **Never batch**", agents)
        self.assertIn("Examples in context:", agents)

    def test_worktree_isolation_robustness_514(self):
        """Regression test for #514: pr_babysit exposes cleanup_git_locks + verify_worktree_is_isolated; rebase and babysit local-rebase paths use them; guidance/AGENTS/persona require verify + lock cleanup before worktree ops (no main checkout pollution)."""
        import plate_core.pr_babysit as pbmod
        self.assertTrue(hasattr(pbmod, "cleanup_git_locks"))
        self.assertTrue(hasattr(pbmod, "verify_worktree_is_isolated"))
        doc = getattr(pbmod, "__doc__", "") or ""
        self.assertIn("Worktree isolation for local-rebase (and general PR fix/babysit flows) is now more robust", doc)
        self.assertIn("(Addresses #514.)", doc)

        # Helpers are callable and return expected shape
        c = pbmod.cleanup_git_locks()
        self.assertIn("cleaned", c)
        self.assertIn("errors", c)
        v = pbmod.verify_worktree_is_isolated()
        self.assertIn("is_isolated", v)
        self.assertIn("toplevel", v)

        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        self.assertIn("verify_worktree_is_isolated", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("cleanup_git_locks", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("(Addresses #514.)", QUIET_OPERATIONS_GUIDANCE)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("call cleanup_git_locks() + verify_worktree_is_isolated()", agents)
        self.assertIn("Use isolated worktree for *all* PR changes during babysit/fixes (never main checkout)", agents)
        self.assertIn("(Addresses #514.)", agents)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("Follow Full PR Green + worktree verify (#514)", persona)

    def test_proactive_release_status_before_targeting_513(self):
        """Regression test for #513: persona, agent_guidance, AGENTS.md, and pr_babysit docs must require running `gh plate release status` *proactively as the very first step* before any branch targeting, PR creation, or base determination for Bug/Feature work (and before babysit calls)."""
        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("Before any branch/PR/base for Bug/Feature: run `gh plate release status` *first* to get correct --base + fragments", persona)
        self.assertIn("(Addresses #513.)", persona)

        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE
        self.assertIn("Release Status Protocol (mandatory first step for any PR/branch/targeting work)", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("Run `gh plate release status` (or equivalent MCP/CLI surface) *immediately as the very first action*", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("(Addresses #513.)", QUIET_OPERATIONS_GUIDANCE)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("MUST run `gh plate release status` (or inspect the issue's semver track label) *proactively as the very first step before any targeting, branch decision, or `gh pr create`*", agents)
        self.assertIn("MUST run `gh plate release status` *proactively as the very first step* before any targeting/branch/PR decision", agents)
        self.assertIn("(Addresses #513.)", agents)

        import plate_core.pr_babysit as pbmod
        doc = getattr(pbmod, "__doc__", "") or ""
        self.assertIn("Per #513: agents MUST run `gh plate release status` *proactively as the very first step* before calling babysit_pr", doc)

    def test_qanda_follow_through_inconsistency_503(self):
        """Regression test for #503: persona, guidance, and AGENTS must enforce that Q&A options promising 'review the PR'/'babysit'/'address feedback' result in *full execution* (pr-babysit skill, isolated worktree, push to same branch, resolve threads) before next question or progress/done; never merge or advance unaddressed. (Builds on #517/#503 stub.)"""
        from plate_core.agent_guidance import QANDA_CURIOSITY_GUIDANCE
        self.assertIn("If a choice promises \"review the PR\", \"babysit\", \"address feedback\", or similar, the agent *must* fully execute that work using the dedicated pr-babysit skill", QANDA_CURIOSITY_GUIDANCE)
        self.assertIn("Never merge or advance with unaddressed feedback. (Addresses #503, #517.)", QANDA_CURIOSITY_GUIDANCE)

        with open("plugin/agents/plate.agent.md", encoding="utf-8") as f:
            persona = f.read()
        self.assertIn("if option promises review/babysit, fully execute via pr-babysit before next (Addresses #503, #517)", persona)

        with open("AGENTS.md", encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("If option promises review/babysit/address feedback, *must* fully execute via pr-babysit skill + worktree + push same branch + resolve threads before next question or progress/done. Never merge unaddressed.", agents)
        self.assertIn("(Addresses #503, #518, #517, #521 and closes the post-0.6.1 Q&A/babysit stub cluster under #580/#569 polish.)", agents)


if __name__ == "__main__":
    unittest.main()


class AutonomyGuidance480Tests(unittest.TestCase):
    """Feature #480: persona + autonomy_loops guidance + catalog skill."""

    def test_autonomy_loops_section_registered(self):
        from plate_core.agent_guidance import get_agent_guidance_sections, AUTONOMY_LOOPS_GUIDANCE

        sections = get_agent_guidance_sections()
        self.assertIn("autonomy_loops", sections)
        self.assertIn("plate_autonomy_status", AUTONOMY_LOOPS_GUIDANCE)
        self.assertIn("PLATE-AUTONOMY-CYCLE", AUTONOMY_LOOPS_GUIDANCE)
        self.assertIn("PLATE-PROCEDURE-RUN", AUTONOMY_LOOPS_GUIDANCE)
        self.assertIn("risk_tolerance", AUTONOMY_LOOPS_GUIDANCE)

    def test_quiet_exempts_autonomy_markers(self):
        from plate_core.agent_guidance import QUIET_OPERATIONS_GUIDANCE

        self.assertIn("PLATE-AUTONOMY-CYCLE", QUIET_OPERATIONS_GUIDANCE)
        self.assertIn("PLATE-PROCEDURE-RUN", QUIET_OPERATIONS_GUIDANCE)

    def test_plate_persona_routes_autonomy_status(self):
        from pathlib import Path

        for rel in ("plugin/agents/plate.agent.md", ".plugin/agents/plate.agent.md"):
            text = Path(rel).read_text()
            self.assertIn("plate_autonomy_status", text)
            self.assertIn("autonomy_loops", text)
            self.assertIn("#480", text)

    def test_catalog_run_autonomy_cycle_skill(self):
        from pathlib import Path
        import yaml

        data = yaml.safe_load(Path("src/plate_core/data/baseline_catalog.yml").read_text())
        skill_ids = {s["id"] for s in data["skills"]}
        self.assertIn("run-autonomy-cycle", skill_ids)
        pm = next(a for a in data["agents"] if a["id"] == "project-manager")
        self.assertIn("run-autonomy-cycle", pm["primary_skill_ids"])
        self.assertEqual(len(data["agents"]), 15)
