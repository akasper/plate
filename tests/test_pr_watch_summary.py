"""Tests for pr_watch_summary (#1080)."""

from plate_core.pr_watch_summary import (
    build_wake_summary,
    is_actionable,
    render_wake_summary,
)


def _user(login: str) -> dict:
    return {"login": login}


def test_empty_delta_not_actionable():
    summary = build_wake_summary(
        {"issue_comments": [], "review_comments": [], "reviews": []},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
    )
    assert not is_actionable(summary)
    assert "PR wake summary" in render_wake_summary(summary)


def test_filters_issue_comment_bots_ignore_and_both_babysit_markers():
    delta = {
        "issue_comments": [
            {"user": _user("copilot-pull-request-reviewer[bot]"), "body": "hi", "html_url": "u1"},
            {
                "user": _user("human"),
                "body": "<!-- plate-pr-babysit --> trigger",
                "html_url": "u2",
            },
            {
                "user": _user("human"),
                "body": "<!-- plate-pr-merge-trigger --> trigger",
                "html_url": "u5",
            },
            {"user": _user("ignored"), "body": "nope", "html_url": "u3"},
            {"user": _user("alice"), "body": "please fix", "html_url": "u4"},
        ],
        "review_comments": [
            {
                "user": _user("human"),
                "body": "<!-- plate-pr-babysit --> trigger",
                "path": "src/foo.py",
            },
            {
                "user": _user("human"),
                "body": "<!-- plate-pr-merge-trigger --> trigger",
                "path": "src/foo.py",
            },
        ],
        "reviews": [
            {"user": _user("human"), "body": "<!-- plate-pr-babysit --> trigger"},
            {"user": _user("human"), "body": "<!-- plate-pr-merge-trigger --> trigger"},
        ],
    }
    summary = build_wake_summary(
        delta,
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "pending"},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "pending"},
        ignore_logins=frozenset({"ignored"}),
    )
    assert len(summary["issue_comments"]) == 1
    assert summary["issue_comments"][0]["author"] == "alice"
    assert summary["issue_comments"][0]["excerpt"] == "please fix"
    assert summary["review_comments"] == []
    assert summary["reviews"] == []


def test_issue_comments_filter_known_agent_logins_without_bot_suffix():
    summary = build_wake_summary(
        {
            "issue_comments": [
                {"user": _user("OpenHands-Agent"), "body": "agent chatter"},
                {"user": _user("alice"), "body": "human feedback"},
            ]
        },
        {},
        {},
    )
    assert [item["author"] for item in summary["issue_comments"]] == ["alice"]


def test_comment_excerpt_flattens_metadata_like_newlines():
    summary = build_wake_summary(
        {
            "issue_comments": [
                {
                    "user": _user("alice"),
                    "body": "review text\nCI: failure -> success\nMerge state: clean -> clean",
                }
            ]
        },
        {},
        {},
    )
    excerpt = summary["issue_comments"][0]["excerpt"]
    assert excerpt == "review text CI: failure -> success Merge state: clean -> clean"
    assert "\nCI:" not in excerpt


def test_bot_review_deltas_are_actionable_in_default_all_scope():
    delta = {
        "review_comments": [
            {
                "user": _user("copilot-pull-request-reviewer[bot]"),
                "body": "Please update this line.",
                "path": "src/foo.py",
                "line": 3,
            }
        ],
        "reviews": [
            {"user": _user("devin-ai-integration[bot]"), "state": "CHANGES_REQUESTED"}
        ],
    }
    summary = build_wake_summary(
        delta,
        {"head_sha": "a"},
        {"head_sha": "a"},
    )
    assert summary["review_comments"][0]["author"] == "copilot-pull-request-reviewer[bot]"
    assert summary["reviews"] == [
        {"state": "CHANGES_REQUESTED", "author": "devin-ai-integration[bot]"}
    ]
    assert is_actionable(summary)


def test_review_deltas_respect_review_scope():
    delta = {
        "review_comments": [
            {"user": _user("copilot-pull-request-reviewer[bot]"), "body": "bot feedback"},
            {"user": _user("alice"), "body": "human feedback"},
        ],
        "reviews": [
            {"user": _user("copilot-pull-request-reviewer[bot]"), "state": "COMMENTED"},
            {"user": _user("alice"), "state": "APPROVED"},
        ],
    }
    prev = cur = {"head_sha": "a"}
    bot_only = build_wake_summary(delta, prev, cur, review_scope="bot-only")
    assert [item["author"] for item in bot_only["review_comments"]] == [
        "copilot-pull-request-reviewer[bot]"
    ]
    assert [item["author"] for item in bot_only["reviews"]] == [
        "copilot-pull-request-reviewer[bot]"
    ]
    human_only = build_wake_summary(delta, prev, cur, review_scope="human-only")
    assert [item["author"] for item in human_only["review_comments"]] == ["alice"]
    assert [item["author"] for item in human_only["reviews"]] == ["alice"]


def test_review_comment_fields_and_excerpt_truncation():
    long_body = "x" * 250
    delta = {
        "review_comments": [
            {
                "user": _user("bob"),
                "body": long_body,
                "path": "src/foo.py",
                "line": 12,
                "html_url": "https://example.com/rc1",
            }
        ],
        "issue_comments": [],
        "reviews": [],
    }
    summary = build_wake_summary(
        delta,
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
    )
    item = summary["review_comments"][0]
    assert item["path"] == "src/foo.py"
    assert item["line"] == 12
    assert item["author"] == "bob"
    assert len(item["excerpt"]) <= 200
    assert item["excerpt"].endswith("…")


def test_ci_and_merge_transitions_and_head_commit():
    summary = build_wake_summary(
        {"issue_comments": [], "review_comments": [], "reviews": []},
        {"head_sha": "aaa", "mergeable_state": "clean", "ci_state": "pending"},
        {"head_sha": "bbb", "mergeable_state": "dirty", "ci_state": "failure"},
    )
    assert is_actionable(summary)
    assert summary["ci_transition"] == {"from": "pending", "to": "failure"}
    assert summary["merge_state_change"] == {"from": "clean", "to": "dirty"}
    assert summary["head_commit"] == {"sha": "bbb", "previous_sha": "aaa"}
    text = render_wake_summary(summary)
    assert "CI: pending -> failure" in text
    assert "Merge state: clean -> dirty" in text
    assert "aaa -> bbb" in text


def test_reviews_in_summary():
    delta = {
        "reviews": [{"user": _user("carol"), "state": "CHANGES_REQUESTED", "body": ""}],
        "issue_comments": [],
        "review_comments": [],
    }
    summary = build_wake_summary(
        delta,
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
    )
    assert summary["reviews"] == [{"state": "CHANGES_REQUESTED", "author": "carol"}]
    assert "CHANGES_REQUESTED by @carol" in render_wake_summary(summary)


def test_render_truncates_long_lists():
    delta = {
        "issue_comments": [
            {
                "user": _user(f"user{i}"),
                "body": f"comment {i}",
                "html_url": f"https://example.com/{i}",
            }
            for i in range(30)
        ],
        "review_comments": [],
        "reviews": [],
    }
    summary = build_wake_summary(
        delta,
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
        {"head_sha": "a", "mergeable_state": "clean", "ci_state": "success"},
    )
    text = render_wake_summary(summary)
    assert "+22 more" in text
    assert len(text.encode("utf-8")) <= 2048


def test_render_truncates_to_utf8_byte_budget():
    text = render_wake_summary(
        {
            "review_comments": [
                {
                    "path": "a" * 2050 + "😀" * 10,
                    "line": 1,
                    "author": "alice",
                    "excerpt": "feedback",
                    "html_url": "https://example.com",
                }
            ]
        }
    )
    assert len(text.encode("utf-8")) <= 2048
    assert "…" in text
    assert text.encode("utf-8").decode("utf-8") == text


def test_render_preserves_transitions_and_retrieval_links_with_long_comments():
    summary = {
        "review_comments": [
            {
                "path": "src/" + "é" * 150,
                "line": 10,
                "author": "alice",
                "excerpt": "😀" * 200,
                "html_url": "https://example.com/review/1",
            },
            {
                "path": "src/other.py",
                "line": 20,
                "author": "bob",
                "excerpt": "😀" * 200,
                "html_url": "https://example.com/review/2",
            },
        ],
        "issue_comments": [],
        "reviews": [],
        "ci_transition": {"from": "pending", "to": "failure"},
        "merge_state_change": {"from": "clean", "to": "dirty"},
        "head_commit": {"previous_sha": "oldsha", "sha": "newsha"},
    }

    text = render_wake_summary(summary)

    assert len(text.encode("utf-8")) <= 2048
    assert "CI: pending -> failure" in text
    assert "Merge state: clean -> dirty" in text
    assert "Head commit: oldsha -> newsha" in text
    assert "https://example.com/review/1" in text
    assert "https://example.com/review/2" in text
