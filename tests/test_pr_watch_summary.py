"""Tests for pr_watch_summary (#1080)."""

from plate_core.pr_watch_summary import (
    BABYSIT_BODY_MARKER,
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


def test_filters_bots_ignore_and_babysit_marker():
    delta = {
        "issue_comments": [
            {"user": _user("copilot-pull-request-reviewer[bot]"), "body": "hi", "html_url": "u1"},
            {
                "user": _user("human"),
                "body": f"{BABYSIT_BODY_MARKER} trigger",
                "html_url": "u2",
            },
            {"user": _user("ignored"), "body": "nope", "html_url": "u3"},
            {"user": _user("alice"), "body": "please fix", "html_url": "u4"},
        ],
        "review_comments": [],
        "reviews": [],
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
