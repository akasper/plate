"""PR gate: integration base must match release status policy (#1449)."""

from __future__ import annotations

import argparse
import json
import sys

from plate_core.branch_policy import (
    INTEGRATION_BASE_FAILURE_HEADING,
    evaluate_integration_branch_policy,
)
from plate_core.release import get_release_status


def parse_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def run_gate(
    *,
    base: str,
    head: str,
    labels: list[str],
    repo: str | None,
    release_status_json: str | None = None,
) -> int:
    if release_status_json:
        payload = json.loads(release_status_json)
        mode = str(payload.get("release_branch_mode") or "legacy")
        tracks = payload.get("release_track_branches") or {}
    else:
        status = get_release_status(repo)
        mode = status.release_branch_mode
        tracks = status.release_track_branches
    failures = evaluate_integration_branch_policy(
        base=base,
        head=head,
        labels=labels,
        release_branch_mode=mode,
        release_track_branches=tracks if isinstance(tracks, dict) else {},
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
    parser.add_argument("--repo", default=None, help="owner/name (default: gh resolution)")
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
        release_status_json=args.release_status_json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
