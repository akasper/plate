"""Auto-close linked issues after merge to PLATE integration branches (#427).

GitHub only auto-closes via closing keywords when the PR merges to the *default*
branch (usually `main`). PLATE Feature/Bug work merges to `release` / `release-*`
/ `epic/*` first, so issues stay open with only `status:implemented` (#556).

This module provides pure helpers used by CI (and tests) to:
- detect integration base branches
- parse Closes/Fixes/Resolves issue numbers from PR bodies
- decide which issue types are safe to auto-close (skip Epic/Task/Release)
- build an auditable close plan
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from plate_core.issue_status_lifecycle import should_apply_status_implemented
from plate_core.pr_gates_closing import parse_strict_closing_issue_numbers

# Issue type labels that must never be auto-closed by integration merge
_SKIP_CLOSE_TYPES = frozenset({"Epic", "Task", "Release"})

# PLATE issue type labels (``label-check``); excluding these means no typed issue.
_PLATE_ISSUE_TYPE_LABELS = frozenset(
    {
        "Bug",
        "Feature",
        "Epic",
        "Release",
        "Research",
        "Design",
        "Question",
        "Task",
        "Audit",
        "Migration",
        "Feedback Response",
        "Spike",
        "Documentation",
    }
)

# Subset of issue types that may be auto-closed when ``Closes`` lands on integration
_CLOSABLE_TYPES = frozenset(
    {
        "Bug",
        "Feature",
        "Research",
        "Design",
        "Question",
        "Audit",
        "Migration",
        "Feedback Response",
        "Spike",
        "Documentation",
    }
)

MARKER_BEGIN = "<!-- PLATE-INTEGRATION-CLOSE:BEGIN -->"
MARKER_END = "<!-- PLATE-INTEGRATION-CLOSE:END -->"


def is_integration_branch(ref: str | None) -> bool:
    """True for PLATE integration bases: release, release-*, epic/*."""
    if not ref:
        return False
    name = ref.replace("refs/heads/", "").strip()
    if not name or name == "main":
        return False
    if name == "release" or name.startswith("release-") or name.startswith("release/"):
        return True
    if name.startswith("epic/") or name.startswith("epic-"):
        return True
    return False


def parse_closing_issue_numbers(body: str | None) -> list[int]:
    """Extract unique issue numbers from closing keywords in PR body order (#1231 strict)."""
    return parse_strict_closing_issue_numbers(body)


def should_auto_close_issue(
    labels: Iterable[str] | None,
    *,
    state: str = "open",
) -> dict[str, Any]:
    """Return {close: bool, reason: str} for an issue given its labels/state."""
    labs = {str(x) for x in (labels or [])}
    st = (state or "open").lower()
    if st != "open":
        return {"close": False, "reason": f"already_{st}"}
    skip = labs & _SKIP_CLOSE_TYPES
    if skip:
        return {"close": False, "reason": f"skip_type:{','.join(sorted(skip))}"}
    type_hits = labs & _PLATE_ISSUE_TYPE_LABELS
    if not type_hits:
        return {"close": False, "reason": "no_issue_type_label"}
    closable = type_hits & _CLOSABLE_TYPES
    if closable:
        return {"close": True, "reason": "closable_type"}
    # Typed issue that is not auto-closed (for example only ``Epic`` — should be
    # caught by ``skip`` above; remaining hits are unexpected combinations).
    return {"close": False, "reason": f"skip_type:{','.join(sorted(type_hits))}"}


def plan_integration_closes(
    *,
    base_ref: str | None,
    pr_body: str | None,
    pr_number: int | None = None,
    issues: list[dict[str, Any]] | None = None,
    has_pr_payload: bool = True,
) -> dict[str, Any]:
    """Build an auditable plan: which issues to label/close after integration merge.

    `issues` optional pre-fetched rows: {number, state, labels: [str]}.
    When omitted, plan only lists numbers parsed from the body (fetch later).

    ``has_pr_payload`` should be False for ``push`` events with no pull request
    payload (the mark-implemented job cannot parse ``Closes`` from a PR body).
    """
    base = (base_ref or "").replace("refs/heads/", "")
    if not is_integration_branch(base):
        return {
            "action": "skip",
            "reason": "not_integration_branch",
            "base_ref": base,
            "to_label": [],
            "to_close": [],
            "skipped": [],
            "parsed": [],
        }

    if not has_pr_payload:
        return {
            "action": "skip",
            "reason": "push_event_no_pr_body",
            "base_ref": base,
            "to_label": [],
            "to_close": [],
            "skipped": [],
            "parsed": [],
            "pr_number": pr_number,
        }

    parsed = parse_closing_issue_numbers(pr_body)
    if not parsed:
        return {
            "action": "skip",
            "reason": "no_closing_keywords",
            "base_ref": base,
            "to_label": [],
            "to_close": [],
            "skipped": [],
            "parsed": [],
            "pr_number": pr_number,
        }

    by_num = {int(i["number"]): i for i in (issues or []) if i.get("number") is not None}
    to_label: list[int] = []
    to_close: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for num in parsed:
        row = by_num.get(num)
        if row is None:
            # Unknown until fetch: plan label + close attempt (workflow resolves labels).
            to_label.append(num)
            to_close.append({"number": num, "reason": "pending_fetch"})
            continue
        labs = row.get("labels") or []
        if isinstance(labs, list) and labs and isinstance(labs[0], dict):
            labs = [x.get("name") for x in labs if x.get("name")]
        labs_list = [x for x in labs if x]
        decision = should_auto_close_issue(labs_list, state=str(row.get("state") or "open"))
        if should_apply_status_implemented(labs_list):
            to_label.append(num)
        if decision["close"]:
            to_close.append({"number": num, "reason": decision["reason"]})
        else:
            skipped.append({"number": num, "reason": decision["reason"]})

    return {
        "action": "apply",
        "reason": "integration_merge",
        "base_ref": base,
        "pr_number": pr_number,
        "parsed": parsed,
        "to_label": to_label,
        "to_close": to_close,
        "skipped": skipped,
    }


def render_close_comment(
    *,
    pr_number: int,
    base_ref: str,
    reason: str = "closing_keyword",
) -> str:
    """Markdown comment body for auto-closed issues (auditable)."""
    payload = {
        "pr": pr_number,
        "base": base_ref,
        "reason": reason,
    }
    import json

    return (
        f"Auto-closed after merge of #{pr_number} into `{base_ref}` "
        f"(PLATE integration-branch close, #427).\n\n"
        f"{MARKER_BEGIN}\n"
        f"{json.dumps(payload)}\n"
        f"{MARKER_END}\n"
    )
