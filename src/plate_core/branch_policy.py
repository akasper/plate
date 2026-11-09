"""Shared PR branch targeting policy for preflight, CI, and verify (#1448 / #1449).

Single source of truth for which base/head pairs are allowed. Complements
``check_main_source`` (illegal feature sources into ``main``) with positive
integration-base targeting and validated epic-branch exceptions.
"""

from __future__ import annotations

from .pr_gates_checks import (
    GateFailure,
    check_integration_base_branch,
    check_main_source,
    is_allowed_main_source_head,
    normalize_label_list,
    resolve_integration_base,
)

INTEGRATION_BASE_FAILURE_HEADING = "integration-base"

_ISSUE_DRIVEN_PR_TYPES = frozenset({"Feature", "Bug", "Documentation"})


def _ref_name(ref: str | None) -> str:
    if not ref:
        return ""
    return ref.replace("refs/heads/", "").strip()


def is_epic_branch_ref(ref: str | None) -> bool:
    name = _ref_name(ref)
    return name.startswith("epic/") or name.startswith("epic-")


def is_valid_epic_base_for_head(base: str | None, head: str | None) -> bool:
    """Allow ``epic/*`` bases only when the head clearly belongs to that epic (#1448)."""
    base_name = _ref_name(base)
    head_name = _ref_name(head)
    if not is_epic_branch_ref(base_name):
        return False
    if head_name == base_name:
        return True
    if base_name.startswith("epic/"):
        slug = base_name.split("/", 1)[1]
        if head_name == f"epic/{slug}":
            return True
        if head_name.startswith(f"epic/{slug}/"):
            return True
    if base_name.startswith("epic-"):
        slug = base_name[5:]
        if head_name.startswith(f"epic-{slug}-") or head_name == base_name:
            return True
    return False


def requires_integration_base_target(labels: list[str]) -> bool:
    return bool(_ISSUE_DRIVEN_PR_TYPES & set(normalize_label_list(labels)))


def is_release_ceremony_pr(
    labels: list[str],
    *,
    base: str | None,
    head: str | None,
) -> bool:
    """Release PR: labeled Release, targets main from an allowed release head."""
    labs = normalize_label_list(labels)
    if "Release" not in labs:
        return False
    base_ref = _ref_name(base)
    if base_ref != "main":
        return False
    return is_allowed_main_source_head(head) and check_main_source(base, head, labels) is None


def evaluate_integration_branch_policy(
    *,
    base: str | None,
    head: str | None,
    labels: list[str],
    release_branch_mode: str,
    release_track_branches: dict[str, bool] | None,
    issue_labels: list[str] | None = None,
) -> list[GateFailure]:
    """Integration-base failures only (no main-source, no release-window)."""
    if not requires_integration_base_target(labels):
        return []
    if is_release_ceremony_pr(labels, base=base, head=head):
        return []

    base_ref = _ref_name(base)
    if base_ref == "main":
        return []
    if is_valid_epic_base_for_head(base, head):
        return []

    resolution = resolve_integration_base(
        release_branch_mode=release_branch_mode,
        release_track_branches=release_track_branches,
        pr_labels=labels,
        issue_labels=issue_labels,
    )
    if resolution.error:
        return [GateFailure("base_branch", resolution.error)]
    expected = resolution.expected
    if expected is None:
        return [
            GateFailure(
                "base_branch",
                "No release integration branches are configured. "
                "Run `gh plate bootstrap --apply` to create standing release branches, "
                "then `gh plate release status` to confirm the integration base.",
            )
        ]
    failure = check_integration_base_branch(
        base,
        expected=expected,
        release_branch_mode=release_branch_mode,
        head=head,
    )
    return [failure] if failure else []


def evaluate_full_branch_policy(
    *,
    base: str | None,
    head: str | None,
    labels: list[str],
    release_branch_mode: str,
    release_track_branches: dict[str, bool] | None,
    issue_labels: list[str] | None = None,
) -> list[GateFailure]:
    """Main-source plus integration-base policy."""
    failures: list[GateFailure] = []
    main_fail = check_main_source(base, head, labels)
    if main_fail:
        failures.append(main_fail)
    failures.extend(
        evaluate_integration_branch_policy(
            base=base,
            head=head,
            labels=labels,
            release_branch_mode=release_branch_mode,
            release_track_branches=release_track_branches,
            issue_labels=issue_labels,
        )
    )
    return failures
