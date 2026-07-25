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

# Closing keywords (GitHub-compatible, case-insensitive)
_CLOSING_RE = re.compile(
    r"\b(closes?|closed|fixe?s?|fixed|resolve[sd]?)\s+"
    r"(?:https?://github\.com/[^/\s]+/[^/\s]+/issues/)?#?(\d+)\b",
    re.IGNORECASE,
)

# Issue type labels that must never be auto-closed by integration merge
_SKIP_CLOSE_TYPES = frozenset({"Epic", "Task", "Release"})

# Types we expect to close when Closes is present
_CLOSABLE_TYPES = frozenset(
    {
        "Bug",
        "Feature",
        "Documentation",
        "Research",
        "Design",
        "Question",
        "Audit",
        "Migration",
        "Feedback Response",
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
    """Extract unique issue numbers from closing keywords in PR body order."""
    if not body:
        return []
    seen: set[int] = set()
    out: list[int] = []
    for m in _CLOSING_RE.finditer(body):
        num = int(m.group(2))
        if num not in seen:
            seen.add(num)
            out.append(num)
    return out


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
    if labs & _CLOSABLE_TYPES:
        return {"close": True, "reason": "closable_type"}
    # No recognized type: still close if Closes was explicit (safe default for
    # unlabeled historical issues) — but prefer skip when only process labels.
    if not labs:
        return {"close": True, "reason": "unlabeled_explicit_closes"}
    return {"close": True, "reason": "explicit_closes_default"}


def plan_integration_closes(
    *,
    base_ref: str | None,
    pr_body: str | None,
    pr_number: int | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an auditable plan: which issues to label/close after integration merge.

    `issues` optional pre-fetched rows: {number, state, labels: [str]}.
    When omitted, plan only lists numbers parsed from the body (fetch later).
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
            # unknown: still label + attempt close (CI will 404-skip if missing)
            to_label.append(num)
            to_close.append({"number": num, "reason": "pending_fetch"})
            continue
        labs = row.get("labels") or []
        if isinstance(labs, list) and labs and isinstance(labs[0], dict):
            labs = [x.get("name") for x in labs if x.get("name")]
        decision = should_auto_close_issue(labs, state=str(row.get("state") or "open"))
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
