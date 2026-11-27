"""Helpers for release.yml publisher verification (#1488 / PR #1523)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any
from urllib.parse import quote

PUBLISHER_WORKFLOW_FILES = (
    "publish-pypi.yml",
    "publish-gh-plate-extension.yml",
)

_SUCCESS_CONCLUSIONS = frozenset({"success"})
MISSING_RUN_ERROR = "no_matching_run_for_release_tag_or_head_sha"


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


def _normalize_api_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "databaseId": run.get("id"),
        "headBranch": run.get("head_branch"),
        "headSha": run.get("head_sha"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "createdAt": run.get("created_at"),
        "workflowPath": run.get("path"),
    }


def _workflow_path_matches(run: dict[str, Any], workflow_file: str) -> bool:
    path = (run.get("workflowPath") or run.get("path") or "").strip()
    if not path:
        return True
    return path == workflow_file or path.endswith(f"/{workflow_file}")


def _gh_api_paginated(endpoint: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["gh", "api", endpoint, "--paginate"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"gh api failed: {endpoint}")
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # gh --paginate may emit one JSON object per page; accept a single page object.
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines:
            return []
        payload = json.loads(lines[0])
    if isinstance(payload, list):
        items: list[dict[str, Any]] = []
        for entry in payload:
            if isinstance(entry, dict) and "workflow_runs" in entry:
                items.extend(entry.get("workflow_runs") or [])
            elif isinstance(entry, dict) and entry.get("id") is not None:
                items.append(entry)
        return items
    if isinstance(payload, dict):
        return list(payload.get("workflow_runs") or [])
    raise RuntimeError(f"unexpected gh api payload for {endpoint}")


def list_workflow_runs_for_publisher(
    repo: str,
    workflow_file: str,
    *,
    release_tag: str,
    head_sha: str,
) -> list[dict[str, Any]]:
    """List matching workflow runs via paginated GitHub API (head SHA + tag branch)."""
    owner, name = repo.split("/", 1)
    endpoints = [
        f"repos/{owner}/{name}/actions/runs?head_sha={quote(head_sha)}&per_page=100",
        f"repos/{owner}/{name}/actions/runs?branch={quote(release_tag)}&per_page=100",
    ]
    by_id: dict[int, dict[str, Any]] = {}
    for endpoint in endpoints:
        for raw in _gh_api_paginated(endpoint):
            if not _workflow_path_matches(raw, workflow_file):
                continue
            normalized = _normalize_api_run(raw)
            run_id = normalized.get("databaseId")
            if run_id is None:
                continue
            by_id[int(run_id)] = normalized
    return list(by_id.values())


def _gh_fetch_run(repo: str, run_id: int) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    proc = subprocess.run(
        ["gh", "api", f"repos/{owner}/{name}/actions/runs/{run_id}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"gh api run {run_id} failed")
    return _normalize_api_run(json.loads(proc.stdout or "{}"))


def _gh_run_watch(repo: str, run_id: int) -> int:
    proc = subprocess.run(
        ["gh", "run", "watch", str(run_id), "--repo", repo, "--exit-status"],
        check=False,
    )
    return int(proc.returncode)


def _missing_run_result(
    workflow_file: str,
    *,
    release_tag: str,
    head_sha: str,
    last_seen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "workflow": workflow_file,
        "run": last_seen,
        "error": MISSING_RUN_ERROR,
        "message": (
            f"No workflow run for {workflow_file} matching release tag "
            f"{release_tag!r} or head SHA {head_sha!r}."
        ),
    }


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
        runs = list_workflow_runs_for_publisher(
            repo,
            workflow_file,
            release_tag=release_tag,
            head_sha=head_sha,
        )
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
                _gh_run_watch(repo, int(run_id))
                refreshed = _gh_fetch_run(repo, int(run_id))
                last_seen = refreshed
                if publisher_run_succeeded(refreshed):
                    return {"ok": True, "run": refreshed, "workflow": workflow_file}
                return {
                    "ok": False,
                    "run": refreshed,
                    "workflow": workflow_file,
                    "error": f"conclusion={refreshed.get('conclusion')}",
                }
        time.sleep(poll_seconds)
    if last_seen is None:
        return _missing_run_result(
            workflow_file, release_tag=release_tag, head_sha=head_sha
        )
    return _missing_run_result(
        workflow_file,
        release_tag=release_tag,
        head_sha=head_sha,
        last_seen=last_seen,
    )


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
    if not summary.get("ok"):
        for item in summary.get("results") or []:
            message = item.get("message")
            if message:
                print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())