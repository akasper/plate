"""Wake summaries for PR babysit watch: deltas only, no full PR reload (#1080)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pr_babysit import _author_in_scope, _default_agent_match, resolve_pr_review_scope

_SUGGESTION_FENCE = re.compile(r"```suggestion\s*([\s\S]*?)```", re.IGNORECASE)

_COPILOT_REVIEWER_LOGINS = frozenset(
    {"copilot", "copilot-pull-request-reviewer[bot]"}
)

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
    return _default_agent_match(login)


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
    text = " ".join((body or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _is_copilot_reviewer(login: str) -> bool:
    return login.lower() in _COPILOT_REVIEWER_LOGINS


def _normalize_comment_body(body: str) -> str:
    def _normalize_fence(match: re.Match[str]) -> str:
        inner = " ".join((match.group(1) or "").lower().split())
        return f"```suggestion {inner}```"

    text = _SUGGESTION_FENCE.sub(_normalize_fence, body or "")
    return " ".join(text.lower().split())


def _comment_line_range(comment: Mapping[str, Any]) -> tuple[str, str]:
    start = comment.get("original_start_line")
    if start is None:
        start = comment.get("start_line")
    end = comment.get("original_line")
    if end is None:
        end = comment.get("line")
    return (
        str(start if start is not None else ""),
        str(end if end is not None else ""),
    )


def comment_fingerprint(comment: Mapping[str, Any]) -> str:
    """Stable fingerprint for a review comment (path, lines, body, author)."""
    path = str(comment.get("path") or "")
    start_str, end_str = _comment_line_range(comment)
    body = _normalize_comment_body(str(comment.get("body") or ""))
    author = _login(comment.get("user")).lower()
    payload = f"{path}\0{start_str}\0{end_str}\0{body}\0{author}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


@dataclass
class ResolvedLedger:
    """Fingerprints of review comments already resolved on this PR."""

    fingerprints: set[str] = field(default_factory=set)

    def to_json(self) -> dict[str, list[str]]:
        return {"fingerprints": sorted(self.fingerprints)}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> ResolvedLedger:
        raw = data.get("fingerprints") or []
        return cls(fingerprints={str(item) for item in raw})


def resolved_path(repo: str, pr: int | str, root: str | Path | None = None) -> Path:
    """Path to the per-PR resolved-comment ledger under .agentic/babysit/."""
    owner, name = repo.split("/", 1)
    base = Path(root or ".") / ".agentic" / "babysit"
    return base / f"{owner}-{name}-{pr}.resolved.json"


def load_resolved(path: str | Path) -> ResolvedLedger:
    file_path = Path(path)
    if not file_path.is_file():
        return ResolvedLedger()
    with file_path.open(encoding="utf-8") as handle:
        return ResolvedLedger.from_json(json.load(handle))


def save_resolved(path: str | Path, ledger: ResolvedLedger) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(ledger.to_json(), handle, indent=2)
        handle.write("\n")


def mark_resolved(ledger: ResolvedLedger, comments: Sequence[Mapping[str, Any]]) -> None:
    for comment in comments:
        ledger.fingerprints.add(comment_fingerprint(comment))


def _filter_review_comments(
    items: Sequence[Mapping[str, Any]],
    ignore_logins: frozenset[str],
    review_scope: str,
    agent_logins: str | None,
    resolved: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    suppressed_repeats = 0
    for raw in items:
        login = _login(raw.get("user"))
        if _should_drop_review(
            str(raw.get("body") or ""), login, ignore_logins, review_scope, agent_logins
        ):
            continue
        if (
            resolved
            and _is_copilot_reviewer(login)
            and comment_fingerprint(raw) in resolved
        ):
            suppressed_repeats += 1
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
    return out, suppressed_repeats


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
    resolved: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Build a structured wake summary from REST deltas and lightweight PR snapshots."""
    effective_review_scope = resolve_pr_review_scope(review_scope)
    review_comments, suppressed_repeats = _filter_review_comments(
        delta.get("review_comments") or [],
        ignore_logins,
        effective_review_scope,
        agent_logins,
        resolved,
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
        "suppressed_repeats": suppressed_repeats,
    }


def is_actionable(summary: Mapping[str, Any]) -> bool:
    """Return True when the summary contains at least one item worth acting on."""
    if summary.get("review_comments") or summary.get("issue_comments") or summary.get("reviews"):
        return True
    if summary.get("ci_transition") or summary.get("merge_state_change") or summary.get("head_commit"):
        return True
    return False


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    if max_bytes <= len("…".encode("utf-8")):
        return encoded[:max_bytes].decode("utf-8", errors="ignore")
    return encoded[: max_bytes - len("…".encode("utf-8"))].decode(
        "utf-8", errors="ignore"
    ) + "…"


def _render_comment_line(
    prefix: str,
    excerpt: str,
    url: str,
    max_bytes: int,
) -> str | None:
    suffix = f" ({url})" if url else ""
    fixed_bytes = len((prefix + suffix).encode("utf-8"))
    if fixed_bytes > max_bytes:
        if len(suffix.encode("utf-8")) >= max_bytes:
            return None
        prefix = _truncate_utf8(prefix, max_bytes - len(suffix.encode("utf-8")))
        fixed_bytes = len((prefix + suffix).encode("utf-8"))
    return prefix + _truncate_utf8(excerpt, max_bytes - fixed_bytes) + suffix


def render_wake_summary(summary: Mapping[str, Any]) -> str:
    """Render a terse, agent-facing wake text (target under ~2 KB)."""
    parts: list[str] = ["PR wake summary"]

    ci = summary.get("ci_transition")
    if ci:
        parts.append(
            f"CI: {_truncate_utf8(str(ci.get('from') or ''), 128)}"
            f" -> {_truncate_utf8(str(ci.get('to') or ''), 128)}"
        )

    merge = summary.get("merge_state_change")
    if merge:
        parts.append(
            f"Merge state: {_truncate_utf8(str(merge.get('from') or ''), 128)}"
            f" -> {_truncate_utf8(str(merge.get('to') or ''), 128)}"
        )

    head = summary.get("head_commit")
    if head:
        prev_sha = head.get("previous_sha") or "(none)"
        parts.append(
            f"Head commit: {_truncate_utf8(str(prev_sha), 128)}"
            f" -> {_truncate_utf8(str(head.get('sha') or ''), 128)}"
        )

    review_comments = summary.get("review_comments") or []
    reviews = summary.get("reviews") or []
    issue_comments = summary.get("issue_comments") or []
    sections: list[tuple[str, list[str | tuple[str, str, str]], int]] = []

    review_lines = []
    for item in review_comments[:_DEFAULT_LIST_CAP]:
        path = _truncate_utf8(str(item.get("path") or ""), 120)
        author = _truncate_utf8(str(item.get("author") or ""), 64)
        prefix = f"{path}:{item.get('line')} @{author}: "
        review_lines.append(
            (prefix, str(item.get("excerpt") or ""), str(item.get("html_url") or ""))
        )
    sections.append(
        (
            "Review comments:",
            review_lines,
            max(0, len(review_comments) - _DEFAULT_LIST_CAP),
        )
    )

    review_lines = [
        f"{_truncate_utf8(str(item.get('state') or ''), 96)} by "
        f"@{_truncate_utf8(str(item.get('author') or ''), 64)}"
        for item in reviews[:_DEFAULT_LIST_CAP]
    ]
    sections.append(
        ("Reviews:", review_lines, max(0, len(reviews) - _DEFAULT_LIST_CAP))
    )

    issue_lines = []
    for item in issue_comments[:_DEFAULT_LIST_CAP]:
        author = _truncate_utf8(str(item.get("author") or ""), 64)
        issue_lines.append(
            (
                f"@{author}: ",
                str(item.get("excerpt") or ""),
                str(item.get("html_url") or ""),
            )
        )
    sections.append(
        (
            "Issue comments:",
            issue_lines,
            max(0, len(issue_comments) - _DEFAULT_LIST_CAP),
        )
    )

    omitted_for_size = 0
    reserve_bytes = 96 if any(lines or omitted for _, lines, omitted in sections) else 0
    for title, lines, omitted in sections:
        if not lines and not omitted:
            continue
        heading = title
        if len("\n".join(parts + [heading]).encode("utf-8")) > (
            RENDER_BYTE_BUDGET - reserve_bytes
        ):
            omitted_for_size += len(lines) + omitted
            continue
        parts.append(heading)
        for line in lines:
            available = (
                RENDER_BYTE_BUDGET
                - reserve_bytes
                - len("\n".join(parts).encode("utf-8"))
                - 3
            )
            if available <= 0:
                omitted_for_size += 1
                continue
            if isinstance(line, tuple):
                shortened_line = _render_comment_line(*line, available)
                if shortened_line is None:
                    omitted_for_size += 1
                    continue
            else:
                shortened_line = _truncate_utf8(line, available)
            parts.append(f"  {shortened_line}")
        if omitted:
            marker = f"  +{omitted} more omitted; fetch full PR details."
            if len("\n".join(parts + [marker]).encode("utf-8")) <= (
                RENDER_BYTE_BUDGET - reserve_bytes
            ):
                parts.append(marker)
            else:
                omitted_for_size += omitted

    if omitted_for_size:
        parts.append(
            "Additional summary content omitted to preserve state changes; "
            "fetch full PR details."
        )
    return "\n".join(parts).strip()
