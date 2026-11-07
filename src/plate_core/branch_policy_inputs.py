"""Shared inputs for branch policy (preflight, CI, verify) (#1449)."""

from __future__ import annotations

from dataclasses import dataclass

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .pr_gates_checks import GateFailure, normalize_label_list, requires_strict_closing_keyword
from .pr_gates_closing import parse_strict_closing_issue_numbers
from .release import ReleaseStatusReport, get_release_status


@dataclass(frozen=True)
class BranchPolicyContext:
    release_status: ReleaseStatusReport
    issue_labels: list[str]


def fetch_labels_for_linked_issues(
    repo: str,
    issue_numbers: list[int],
    *,
    client: GhClient | None = None,
) -> tuple[list[str], str | None]:
    """Return merged label names from linked issues, or an error message."""
    if not issue_numbers:
        return [], None
    gh = client or GhClient()
    target = resolve_repo(repo)
    labels: list[str] = []
    for num in issue_numbers:
        try:
            payload = gh.api(f"repos/{target}/issues/{num}") or {}
        except GhApiError as exc:
            return [], f"Could not load labels for linked issue #{num}: {exc}"
        for item in payload.get("labels") or []:
            name = (item.get("name") or "").strip()
            if name:
                labels.append(name)
    return labels, None


def gather_branch_policy_context(
    *,
    repo: str | None,
    pr_labels: list[str],
    body: str | None,
    client: GhClient | None = None,
    release_status: ReleaseStatusReport | None = None,
) -> tuple[BranchPolicyContext | None, GateFailure | None]:
    """Load release status + linked-issue labels with fail-closed errors."""
    gh = client or GhClient()
    status = release_status or get_release_status(repo, client=gh)
    if status.branch_verification_errors:
        return None, GateFailure(
            "base_branch",
            "Release branch presence is unverified (GitHub API error). "
            + "; ".join(status.branch_verification_errors),
        )
    if status.release_branch_mode == "unverified":
        return None, GateFailure(
            "base_branch",
            "Release branch metadata is unavailable; retry when GitHub API is reachable.",
        )

    issue_labels: list[str] = []
    labs = normalize_label_list(pr_labels)
    if requires_strict_closing_keyword(labs):
        numbers = parse_strict_closing_issue_numbers(body)
        if numbers:
            issue_labels, err = fetch_labels_for_linked_issues(
                status.repo,
                numbers,
                client=gh,
            )
            if err:
                return None, GateFailure("base_branch", err)
        elif body_has_closing_refs_without_strict(body):
            pass
    return BranchPolicyContext(release_status=status, issue_labels=issue_labels), None


def body_has_closing_refs_without_strict(body: str | None) -> bool:
    """Heuristic: body mentions #N but strict parse found nothing (metadata may be incomplete)."""
    text = body or ""
    return "#" in text and not parse_strict_closing_issue_numbers(text)
