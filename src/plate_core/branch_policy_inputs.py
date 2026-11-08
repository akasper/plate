"""Shared inputs for branch policy (preflight, CI, verify) (#1449)."""

from __future__ import annotations

from dataclasses import dataclass

from .github_client import GhClient
from .health import resolve_repo
from .issue_context import IssueContextStatus, resolve_issue_context
from .pr_gates_checks import GateFailure, normalize_label_list, requires_strict_closing_keyword
from .release import ReleaseStatusReport, get_release_status


@dataclass(frozen=True)
class BranchPolicyContext:
    release_status: ReleaseStatusReport
    issue_labels: list[str]


def release_status_from_dict(payload: dict, *, repo: str = "unknown/unknown") -> ReleaseStatusReport:
    tracks = payload.get("release_track_branches") or {}
    return ReleaseStatusReport(
        repo=str(payload.get("repo") or repo),
        release_branch_exists=bool(tracks.get("release")),
        release_track_branches=tracks if isinstance(tracks, dict) else {},
        release_branch_mode=str(payload.get("release_branch_mode") or "legacy"),
        release_branch_reset_target=str(payload.get("release_branch_reset_target") or "main"),
        warnings=list(payload.get("warnings") or []),
        open_release_issues=list(payload.get("open_release_issues") or []),
        current_version=payload.get("current_version"),
        latest_version=payload.get("latest_version"),
        pending_fragment_count=int(payload.get("pending_fragment_count") or 0),
        pending_fragments=[],
        extension_release_checks=list(payload.get("extension_release_checks") or []),
        release_window_open=bool(payload.get("release_window_open")),
        branch_verification_errors=list(payload.get("branch_verification_errors") or []),
    )


def _issue_labels_from_context(
    *,
    pr_repo: str,
    pr_labels: list[str],
    body: str | None,
    pr_number: int | None,
    client: GhClient,
) -> tuple[list[str], GateFailure | None]:
    if not requires_strict_closing_keyword(pr_labels):
        return [], None
    result = resolve_issue_context(
        pr_repo=pr_repo,
        pr_labels=pr_labels,
        body=body,
        pr_number=pr_number,
        client=client,
    )
    if result.status == IssueContextStatus.NOT_REQUIRED:
        return [], None
    if result.status == IssueContextStatus.UNAVAILABLE:
        return [], GateFailure("base_branch", result.message or "Issue context unavailable.")
    if result.status == IssueContextStatus.ABSENT:
        return [], None
    return list(result.labels), None


def gather_branch_policy_context(
    *,
    repo: str | None,
    pr_labels: list[str],
    body: str | None,
    pr_number: int | None = None,
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

    issue_labels, issue_fail = _issue_labels_from_context(
        pr_repo=status.repo,
        pr_labels=normalize_label_list(pr_labels),
        body=body,
        pr_number=pr_number,
        client=gh,
    )
    if issue_fail:
        return None, issue_fail
    return BranchPolicyContext(release_status=status, issue_labels=issue_labels), None
