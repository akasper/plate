"""PR gate: integration base must match release status policy (#1449)."""

from __future__ import annotations

import argparse
import json
import sys

from plate_core.branch_policy import (
    INTEGRATION_BASE_FAILURE_HEADING,
    evaluate_integration_branch_policy,
)
from plate_core.branch_policy_inputs import gather_branch_policy_context
from plate_core.release import ReleaseStatusReport


def parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _status_from_json(payload: dict) -> ReleaseStatusReport:
    tracks = payload.get("release_track_branches") or {}
    return ReleaseStatusReport(
        repo=str(payload.get("repo") or "unknown/unknown"),
        release_branch_exists=bool(tracks.get("release")),
        release_track_branches=tracks if isinstance(tracks, dict) else {},
        release_branch_mode=str(payload.get("release_branch_mode") or "legacy"),
        release_branch_reset_target="main",
        warnings=[],
        open_release_issues=[],
        current_version=None,
        latest_version=None,
        pending_fragment_count=0,
        pending_fragments=[],
        extension_release_checks=[],
        branch_verification_errors=list(payload.get("branch_verification_errors") or []),
    )


def run_gate(
    *,
    base: str,
    head: str,
    labels: list[str],
    repo: str | None,
    body: str | None = None,
    release_status_json: str | None = None,
) -> int:
    label_list = labels
    if release_status_json:
        status = _status_from_json(json.loads(release_status_json))
        ctx, meta_fail = gather_branch_policy_context(
            repo=repo,
            pr_labels=label_list,
            body=body,
            release_status=status,
        )
    else:
        ctx, meta_fail = gather_branch_policy_context(
            repo=repo,
            pr_labels=label_list,
            body=body,
        )
    if meta_fail:
        print(
            "\n".join(
                [
                    f"## ⚠️ {INTEGRATION_BASE_FAILURE_HEADING}",
                    "",
                    meta_fail.message,
                ]
            ),
            file=sys.stderr,
        )
        return 1
    assert ctx is not None
    status = ctx.release_status
    failures = evaluate_integration_branch_policy(
        base=base,
        head=head,
        labels=label_list,
        release_branch_mode=status.release_branch_mode,
        release_track_branches=status.release_track_branches,
        issue_labels=ctx.issue_labels,
    )
    if not failures:
        return 0
    lines = [f"## ⚠️ {INTEGRATION_BASE_FAILURE_HEADING}", ""]
    for failure in failures:
        lines.append(failure.message)
    print("\n".join(lines), file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PLATE integration-base PR gate (#1449)")
    parser.add_argument("--base", required=True, help="PR base ref")
    parser.add_argument("--head", required=True, help="PR head ref")
    parser.add_argument("--labels", default="", help="Comma-separated PR labels")
    parser.add_argument("--body", default="", help="PR body (for linked-issue track labels)")
    parser.add_argument("--repo", default=None, help="owner/name (default: gh repo resolution)")
    parser.add_argument(
        "--release-status-json",
        default=None,
        help="Optional JSON from gh plate release status --json (for hermetic tests)",
    )
    args = parser.parse_args(argv)
    return run_gate(
        base=args.base,
        head=args.head,
        labels=parse_labels(args.labels),
        repo=args.repo,
        body=args.body or None,
        release_status_json=args.release_status_json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
