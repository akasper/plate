"""Helpers for release.yml publisher verification (#1488 / PR #1523)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any

PUBLISHER_WORKFLOW_FILES = (
    "publish-pypi.yml",
    "publish-gh-plate-extension.yml",
)

_SUCCESS_CONCLUSIONS = frozenset({"success"})


def filter_workflow_runs_for_release(
    runs: list[dict[str, Any]],
    *,
    release_tag: str,
    head_sha: str | None = None,
) -> list[dict[str, Any]]:
    """Return runs whose head branch is the release tag or whose head SHA matches."""
    tag = (release_tag or "").strip()
    sha = (head_sha or "").strip().lower()
    matched: list[dict[str, Any]] = []
    for run in runs:
        branch = (run.get("headBranch") or "").strip()
        run_sha = (run.get("headSha") or "").strip().lower()
        if tag and branch == tag:
            matched.append(run)
            continue
        if sha and run_sha == sha:
            matched.append(run)
    return matched


def sort_workflow_runs_by_created(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first by ``createdAt`` (ISO-8601)."""
    return sorted(runs, key=lambda item: item.get("createdAt") or "", reverse=True)


def pick_publisher_workflow_run(
    runs: list[dict[str, Any]],
    *,
    release_tag: str,
    head_sha: str | None = None,
) -> dict[str, Any] | None:
    """Newest matching workflow run by ``createdAt`` (in-flight or completed)."""
    ordered = sort_workflow_runs_by_created(
        filter_workflow_runs_for_release(runs, release_tag=release_tag, head_sha=head_sha)
    )
    return ordered[0] if ordered else None


def publisher_run_succeeded(run: dict[str, Any] | None) -> bool:
    if not run:
        return False
    if (run.get("status") or "").lower() != "completed":
        return False
    conclusion = (run.get("conclusion") or "").lower()
    return conclusion in _SUCCESS_CONCLUSIONS


def should_verify_publishers_for_tag(*, tag_at_merge_sha: bool) -> bool:
    """True when the release tag already points at the merged Release PR commit."""
    return bool(tag_at_merge_sha)


def _gh_run_list(repo: str, workflow_file: str, *, limit: int = 50) -> list[dict[str, Any]]:
    proc = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow_file,
            "--limit",
            str(limit),
            "--json",
            "databaseId,headBranch,headSha,status,conclusion,createdAt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "gh run list failed")
    payload = json.loads(proc.stdout or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("unexpected gh run list payload")
    return payload


def _gh_run_watch(repo: str, run_id: int) -> int:
    proc = subprocess.run(
        ["gh", "run", "watch", str(run_id), "--repo", repo, "--exit-status"],
        check=False,
    )
    return int(proc.returncode)


def wait_for_publisher_workflow(
    repo: str,
    workflow_file: str,
    *,
    release_tag: str,
    head_sha: str,
    poll_attempts: int = 40,
    poll_seconds: int = 15,
) -> dict[str, Any]:
    """Wait until the newest matching run completes; return selection metadata."""
    last_seen: dict[str, Any] | None = None
    for _ in range(poll_attempts):
        runs = _gh_run_list(repo, workflow_file)
        picked = pick_publisher_workflow_run(
            runs, release_tag=release_tag, head_sha=head_sha
        )
        if picked:
            last_seen = picked
            status = (picked.get("status") or "").lower()
            if status == "completed":
                if publisher_run_succeeded(picked):
                    return {"ok": True, "run": picked, "workflow": workflow_file}
                return {
                    "ok": False,
                    "run": picked,
                    "workflow": workflow_file,
                    "error": f"conclusion={picked.get('conclusion')}",
                }
            run_id = picked.get("databaseId")
            if run_id is not None:
                code = _gh_run_watch(repo, int(run_id))
                if code == 0:
                    return {"ok": True, "run": picked, "workflow": workflow_file}
                return {
                    "ok": False,
                    "run": picked,
                    "workflow": workflow_file,
                    "error": f"gh run watch exit {code}",
                }
        time.sleep(poll_seconds)
    return {
        "ok": False,
        "workflow": workflow_file,
        "run": last_seen,
        "error": "no_matching_run",
    }


def wait_for_release_publishers(
    repo: str,
    *,
    release_tag: str,
    head_sha: str,
    workflows: tuple[str, ...] = PUBLISHER_WORKFLOW_FILES,
) -> dict[str, Any]:
    results = []
    for workflow_file in workflows:
        results.append(
            wait_for_publisher_workflow(
                repo,
                workflow_file,
                release_tag=release_tag,
                head_sha=head_sha,
            )
        )
    ok = all(item.get("ok") for item in results)
    return {"ok": ok, "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wait for release publisher workflows")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)
    summary = wait_for_release_publishers(
        args.repo,
        release_tag=args.release_tag,
        head_sha=args.head_sha,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())