"""Wake summaries for PR babysit watch: deltas only, no full PR reload (#1080)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .pr_babysit import _author_in_scope, resolve_pr_review_scope

BABYSIT_BODY_MARKERS = (
    "<!-- plate-pr-babysit -->",
    "<!-- plate-pr-merge-trigger -->",
)
BODY_EXCERPT_MAX = 200
RENDER_BYTE_BUDGET = 2048
_DEFAULT_LIST_CAP = 8


def _login(user: Mapping[str, Any] | None) -> str:
    if not user:
        return ""
    return str(user.get("login") or "")


def _is_bot_login(login: str) -> bool:
    return login.endswith("[bot]")


def _has_babysit_marker(body: str) -> bool:
    return any(marker in body for marker in BABYSIT_BODY_MARKERS)


def _should_drop_comment(body: str | None, login: str, ignore_logins: frozenset[str]) -> bool:
    if not login:
        return True
    if login in ignore_logins:
        return True
    if _is_bot_login(login):
        return True
    if _has_babysit_marker(body or ""):
        return True
    return False


def _should_drop_review(
    body: str | None,
    login: str,
    ignore_logins: frozenset[str],
    review_scope: str,
    agent_logins: str | None,
) -> bool:
    if not login or login in ignore_logins:
        return True
    if _has_babysit_marker(body or ""):
        return True
    if not _author_in_scope(login, scope=review_scope, agent_logins=agent_logins):
        return True
    return False


def _excerpt(body: str | None, limit: int = BODY_EXCERPT_MAX) -> str:
    text = (body or "").replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _filter_review_comments(
    items: Sequence[Mapping[str, Any]],
    ignore_logins: frozenset[str],
    review_scope: str,
    agent_logins: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        login = _login(raw.get("user"))
        if _should_drop_review(
            str(raw.get("body") or ""), login, ignore_logins, review_scope, agent_logins
        ):
            continue
        line = raw.get("line")
        if line is None:
            line = raw.get("original_line")
        out.append(
            {
                "path": raw.get("path") or "",
                "line": line,
                "author": login,
                "excerpt": _excerpt(str(raw.get("body") or "")),
                "html_url": raw.get("html_url") or "",
            }
        )
    return out


def _filter_issue_comments(
    items: Sequence[Mapping[str, Any]],
    ignore_logins: frozenset[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        login = _login(raw.get("user"))
        if _should_drop_comment(str(raw.get("body") or ""), login, ignore_logins):
            continue
        out.append(
            {
                "author": login,
                "excerpt": _excerpt(str(raw.get("body") or "")),
                "html_url": raw.get("html_url") or "",
            }
        )
    return out


def _filter_reviews(
    items: Sequence[Mapping[str, Any]],
    ignore_logins: frozenset[str],
    review_scope: str,
    agent_logins: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        login = _login(raw.get("user"))
        body = str(raw.get("body") or "")
        if _should_drop_review(body, login, ignore_logins, review_scope, agent_logins):
            continue
        out.append(
            {
                "state": raw.get("state") or "",
                "author": login,
            }
        )
    return out


def build_wake_summary(
    delta: Mapping[str, Any],
    prev: Mapping[str, Any],
    cur: Mapping[str, Any],
    *,
    ignore_logins: frozenset[str] = frozenset(),
    review_scope: str | None = None,
    agent_logins: str | None = None,
) -> dict[str, Any]:
    """Build a structured wake summary from REST deltas and lightweight PR snapshots."""
    effective_review_scope = resolve_pr_review_scope(review_scope)
    review_comments = _filter_review_comments(
        delta.get("review_comments") or [],
        ignore_logins,
        effective_review_scope,
        agent_logins,
    )
    issue_comments = _filter_issue_comments(delta.get("issue_comments") or [], ignore_logins)
    reviews = _filter_reviews(
        delta.get("reviews") or [],
        ignore_logins,
        effective_review_scope,
        agent_logins,
    )

    prev_head = prev.get("head_sha")
    cur_head = cur.get("head_sha")
    head_commit: dict[str, str] | None = None
    if cur_head and cur_head != prev_head:
        head_commit = {"sha": str(cur_head), "previous_sha": str(prev_head or "")}

    prev_ci = prev.get("ci_state")
    cur_ci = cur.get("ci_state")
    ci_transition: dict[str, str] | None = None
    if cur_ci != prev_ci and (cur_ci is not None or prev_ci is not None):
        ci_transition = {"from": str(prev_ci or ""), "to": str(cur_ci or "")}

    prev_merge = prev.get("mergeable_state")
    cur_merge = cur.get("mergeable_state")
    merge_state_change: dict[str, str] | None = None
    if cur_merge != prev_merge and (cur_merge is not None or prev_merge is not None):
        merge_state_change = {"from": str(prev_merge or ""), "to": str(cur_merge or "")}

    return {
        "review_comments": review_comments,
        "issue_comments": issue_comments,
        "reviews": reviews,
        "ci_transition": ci_transition,
        "merge_state_change": merge_state_change,
        "head_commit": head_commit,
    }


def is_actionable(summary: Mapping[str, Any]) -> bool:
    """Return True when the summary contains at least one item worth acting on."""
    if summary.get("review_comments") or summary.get("issue_comments") or summary.get("reviews"):
        return True
    if summary.get("ci_transition") or summary.get("merge_state_change") or summary.get("head_commit"):
        return True
    return False


def _render_list_section(
    title: str,
    lines: list[str],
    cap: int,
) -> tuple[list[str], int]:
    """Return rendered lines and count omitted."""
    if not lines:
        return [], 0
    shown = lines[:cap]
    omitted = max(0, len(lines) - len(shown))
    block = [title] + [f"  {line}" for line in shown]
    if omitted:
        block.append(f"  +{omitted} more")
    return block, omitted


def render_wake_summary(summary: Mapping[str, Any]) -> str:
    """Render a terse, agent-facing wake text (target under ~2 KB)."""
    parts: list[str] = ["PR wake summary"]

    rc_lines = [
        f"{item['path']}:{item.get('line')} @{item['author']}: {item['excerpt']} ({item['html_url']})"
        for item in summary.get("review_comments") or []
    ]
    parts.extend(_render_list_section("Review comments:", rc_lines, _DEFAULT_LIST_CAP)[0])

    rev_lines = [
        f"{item['state']} by @{item['author']}" for item in summary.get("reviews") or []
    ]
    parts.extend(_render_list_section("Reviews:", rev_lines, _DEFAULT_LIST_CAP)[0])

    ic_lines = [
        f"@{item['author']}: {item['excerpt']} ({item['html_url']})"
        for item in summary.get("issue_comments") or []
    ]
    parts.extend(_render_list_section("Issue comments:", ic_lines, _DEFAULT_LIST_CAP)[0])

    ci = summary.get("ci_transition")
    if ci:
        parts.append(f"CI: {ci.get('from')} -> {ci.get('to')}")

    merge = summary.get("merge_state_change")
    if merge:
        parts.append(f"Merge state: {merge.get('from')} -> {merge.get('to')}")

    head = summary.get("head_commit")
    if head:
        prev_sha = head.get("previous_sha") or "(none)"
        parts.append(f"Head commit: {prev_sha} -> {head.get('sha')}")

    text = "\n".join(parts).strip()
    if len(text.encode("utf-8")) <= RENDER_BYTE_BUDGET:
        return text

    # Shrink list caps until within budget or minimal.
    cap = _DEFAULT_LIST_CAP
    while cap > 1:
        cap -= 1
        parts = ["PR wake summary"]
        parts.extend(_render_list_section("Review comments:", rc_lines, cap)[0])
        parts.extend(_render_list_section("Reviews:", rev_lines, cap)[0])
        parts.extend(_render_list_section("Issue comments:", ic_lines, cap)[0])
        if ci:
            parts.append(f"CI: {ci.get('from')} -> {ci.get('to')}")
        if merge:
            parts.append(f"Merge state: {merge.get('from')} -> {merge.get('to')}")
        if head:
            prev_sha = head.get("previous_sha") or "(none)"
            parts.append(f"Head commit: {prev_sha} -> {head.get('sha')}")
        text = "\n".join(parts).strip()
        if len(text.encode("utf-8")) <= RENDER_BYTE_BUDGET:
            return text

    encoded = text.encode("utf-8")
    ellipsis = "…"
    prefix = encoded[: RENDER_BYTE_BUDGET - len(ellipsis.encode("utf-8"))]
    return prefix.decode("utf-8", errors="ignore").rstrip() + ellipsis
