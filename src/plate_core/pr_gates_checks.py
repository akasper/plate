"""Shared PLATE PR gate checks for local preflight and plate-pr-gates CI (#1418).

Uses ``pr_gates_closing`` and ``pr_gates_contract``; do not duplicate gate rules elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .pr_gates_closing import body_has_strict_closing_keyword, parse_strict_closing_issue_numbers

PR_TYPE_LABELS: tuple[str, ...] = ("Bug", "Feature", "Documentation", "Feedback Response")
PR_TYPE_BY_LOWER = {name.lower(): name for name in PR_TYPE_LABELS}
ALLOWED_TIER_LABELS = frozenset({"tier:T0", "tier:T1", "tier:T2", "tier:T3"})
AREA_LABEL_RE = re.compile(r"^area:", re.IGNORECASE)
LOOSE_ISSUE_REF_RE = re.compile(r"#(\d+)\b")
REFS_ISSUE_RE = re.compile(r"\bRefs\s+#(\d+)\b", re.IGNORECASE)
TRACK_LABEL_TO_BRANCH = {"Major": "release-major", "Minor": "release-minor", "Patch": "release-patch"}


@dataclass(frozen=True)
class GateFailure:
    check_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.check_id, "message": self.message}


def normalize_label_list(labels: list[str] | None) -> list[str]:
    return [str(x).strip() for x in (labels or []) if str(x).strip()]


def pr_type_matches(labels: list[str]) -> list[str]:
    return [PR_TYPE_BY_LOWER[name.lower()] for name in labels if name.lower() in PR_TYPE_BY_LOWER]


def closing_keyword_fix_message(*, issue_number: int | None = None) -> str:
    if issue_number is not None:
        return f'Add "Closes #{issue_number}" to the PR body.'
    return 'Add "Closes #N" to the PR body (replace N with the issue this PR resolves).'


def suggest_issue_number_for_closing_fix(body: str | None) -> int | None:
    """Prefer explicit Refs #N, else the first bare #N in stripped body."""
    text = body or ""
    ref = REFS_ISSUE_RE.search(text)
    if ref:
        return int(ref.group(1))
    nums = parse_strict_closing_issue_numbers(text)
    if nums:
        return nums[0]
    loose = LOOSE_ISSUE_REF_RE.search(text)
    if loose:
        return int(loose.group(1))
    return None


def requires_strict_closing_keyword(labels: list[str]) -> bool:
    labs = set(normalize_label_list(labels))
    if "no-issue" in labs or "Feedback Response" in labs:
        return False
    return bool(set(PR_TYPE_LABELS) & labs)


def check_pr_type_labels(labels: list[str]) -> GateFailure | None:
    """Same rules as ``labels`` workflow (type + forbidden planning labels)."""
    names = normalize_label_list(labels)
    forbidden = [label for label in names if re.match(r"^(status:|priority:)", label)]
    if forbidden:
        return GateFailure(
            "pr_type_label",
            f"Remove planning state labels ({', '.join(forbidden)}) from the PR; use GitHub Projects fields instead.",
        )
    tier_matches = [label for label in names if label in ALLOWED_TIER_LABELS]
    invalid_tier = [
        label for label in names if label.startswith("tier:") and label not in ALLOWED_TIER_LABELS
    ]
    if invalid_tier:
        allowed = ", ".join(sorted(ALLOWED_TIER_LABELS))
        return GateFailure(
            "pr_type_label",
            f"Remove unsupported tier labels ({', '.join(invalid_tier)}); allowed optional tier labels: {allowed}.",
        )
    if len(tier_matches) > 1:
        allowed = ", ".join(sorted(ALLOWED_TIER_LABELS))
        return GateFailure(
            "pr_type_label",
            f"Use at most one tier label ({allowed}); found: {', '.join(tier_matches)}.",
        )
    matches = pr_type_matches(names)
    if len(matches) == 1:
        return None
    expected = ", ".join(PR_TYPE_LABELS)
    found = ", ".join(matches) if matches else "(none)"
    return GateFailure(
        "pr_type_label",
        f'Pass exactly one type label on create, e.g. `gh pr create --label "{PR_TYPE_LABELS[1]}"` '
        f"(allowed: {expected}); found: {found}.",
    )


def check_feature_area_label(labels: list[str]) -> GateFailure | None:
    matches = pr_type_matches(normalize_label_list(labels))
    if len(matches) != 1 or matches[0] != "Feature":
        return None
    area_labels = [label for label in labels if AREA_LABEL_RE.match(label)]
    if area_labels:
        return None
    return GateFailure(
        "area_label",
        'Add an area label on create, e.g. `gh pr create --label "Feature" --label "area:cli"`.',
    )


def has_feature_release_fragment(changed_paths: list[str]) -> bool:
    for raw in changed_paths:
        path = (raw or "").strip()
        if path.startswith(".agentic/releases/unreleased/") and path.endswith(".json"):
            return True
        if (
            path.startswith(".agentic/releases/")
            and not path.startswith(".agentic/releases/unreleased/")
            and path.endswith(".json")
        ):
            return True
    return False


def check_feature_release_fragment(labels: list[str], changed_paths: list[str]) -> GateFailure | None:
    matches = pr_type_matches(normalize_label_list(labels))
    if len(matches) != 1 or matches[0] != "Feature":
        return None
    if has_feature_release_fragment(changed_paths):
        return None
    return GateFailure(
        "release_fragment",
        "Add a release fragment under `.agentic/releases/unreleased/<slug>.json` "
        "(see `.agentic/releases/unreleased/README.md`).",
    )


def check_strict_closing_keyword(
    body: str | None,
    labels: list[str],
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> GateFailure | None:
    if not requires_strict_closing_keyword(labels):
        return None
    if body_has_strict_closing_keyword(body, owner=owner, repo=repo):
        return None
    issue_num = suggest_issue_number_for_closing_fix(body)
    return GateFailure("closing_keyword", closing_keyword_fix_message(issue_number=issue_num))


def resolve_expected_integration_base(
    *,
    release_branch_mode: str,
    release_track_branches: dict[str, bool] | None,
    pr_labels: list[str],
    issue_labels: list[str] | None = None,
) -> str:
    """Expected --base for Feature/Bug/Documentation work (Release PRs target main)."""
    if "Release" in normalize_label_list(pr_labels):
        return "main"
    tracks = release_track_branches or {}
    combined = set(normalize_label_list(pr_labels)) | set(normalize_label_list(issue_labels))
    mode = (release_branch_mode or "").strip() or "legacy"
    if mode in ("multi-track", "track-only", "hybrid"):
        for track in ("Major", "Minor", "Patch"):
            if track in combined:
                branch = TRACK_LABEL_TO_BRANCH[track]
                if tracks.get(branch):
                    return branch
        for branch in ("release-minor", "release-major", "release-patch"):
            if tracks.get(branch):
                return branch
    if tracks.get("release") or mode == "legacy":
        return "release"
    if tracks.get("release-minor"):
        return "release-minor"
    return "main"


def check_integration_base_branch(
    base: str | None,
    *,
    expected: str,
    release_branch_mode: str,
) -> GateFailure | None:
    got = (base or "").strip()
    if not got:
        return GateFailure(
            "base_branch",
            f"Pass `--base {expected}` (run `gh plate release status` to confirm the integration branch).",
        )
    if got == expected:
        return None
    hint = f"`gh plate release status` reports mode {release_branch_mode!r}."
    return GateFailure(
        "base_branch",
        f"Use `--base {expected}` for this PR (found {got!r}); {hint}",
    )


def run_preflight_gate_checks(
    *,
    body: str | None,
    labels: list[str],
    base: str | None,
    changed_paths: list[str],
    owner: str | None,
    repo: str | None,
    release_branch_mode: str,
    release_track_branches: dict[str, bool] | None,
    issue_labels: list[str] | None = None,
) -> list[GateFailure]:
    failures: list[GateFailure] = []
    for check in (
        check_pr_type_labels(labels),
        check_feature_area_label(labels),
        check_strict_closing_keyword(body, labels, owner=owner, repo=repo),
        check_feature_release_fragment(labels, changed_paths),
    ):
        if check:
            failures.append(check)
    expected = resolve_expected_integration_base(
        release_branch_mode=release_branch_mode,
        release_track_branches=release_track_branches,
        pr_labels=labels,
        issue_labels=issue_labels,
    )
    base_fail = check_integration_base_branch(
        base,
        expected=expected,
        release_branch_mode=release_branch_mode,
    )
    if base_fail:
        failures.append(base_fail)
    return failures


def issue_link_gate_failure_lines(
    body: str | None,
    labels: list[str],
    *,
    owner: str | None = None,
    repo: str | None = None,
    has_sidebar_link: bool = False,
) -> list[str] | None:
    """Return extra failure lines for plate-pr-gates issue-link gate (closing keyword path)."""
    if has_sidebar_link:
        return None
    if not requires_strict_closing_keyword(labels):
        return None
    if body_has_strict_closing_keyword(body, owner=owner, repo=repo):
        return None
    issue_num = suggest_issue_number_for_closing_fix(body)
    return [closing_keyword_fix_message(issue_number=issue_num)]


def preflight_report_dict(
    failures: list[GateFailure],
    *,
    expected_base: str,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "passed": not failures,
        "expected_base": expected_base,
        "labels": normalize_label_list(labels),
        "failures": [item.to_dict() for item in failures],
    }
