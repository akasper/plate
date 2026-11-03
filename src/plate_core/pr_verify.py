"""Scripted pre-merge PR checks for ``gh plate pr verify`` and MCP (#1365).

Read-only: reports pass/fail per check; never merges or mutates GitHub state.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from .github_client import GhApiError, GhClient
from .health import resolve_repo
from .pr_babysit import _detect_base_branch_out_of_sync, _load_pr_data, get_unresolved_review_threads
from .pr_gates_closing import body_has_strict_closing_keyword
from .pr_gates_contract import RECOMMENDED_REQUIRED_CHECK_CONTEXTS
from .pr_watch_guards import (
    compute_raw_ci_state,
    fetch_required_check_contexts,
    missing_required_contexts,
    observed_check_contexts,
)

PR_TYPE_LABELS: tuple[str, ...] = ("Bug", "Feature", "Documentation", "Feedback Response")
PR_TYPE_BY_LOWER = {name.lower(): name for name in PR_TYPE_LABELS}
AREA_LABEL_RE = re.compile(r"^area:", re.IGNORECASE)
UNRELEASED_FRAGMENT_RE = re.compile(
    r"^\.agentic/releases/unreleased/[^/]+\.json$", re.IGNORECASE
)
FAIL_CONCLUSIONS = frozenset(
    {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "error"}
)
STALE_BASE_TEST_COUNT_WARN = 1220


@dataclass
class VerifyCheck:
    id: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "passed": self.passed, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


def _split_repo(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name


def _label_names(pull: dict[str, Any]) -> list[str]:
    labels = pull.get("labels") or []
    out: list[str] = []
    for item in labels:
        if isinstance(item, dict):
            out.append(str(item.get("name") or ""))
        else:
            out.append(str(item))
    return [name for name in out if name]


def _pr_type_labels(labels: list[str]) -> list[str]:
    return [PR_TYPE_BY_LOWER[name.lower()] for name in labels if name.lower() in PR_TYPE_BY_LOWER]


def _run_sort_key(run: dict[str, Any]) -> tuple[str, int]:
    return (str(run.get("started_at") or run.get("updated_at") or ""), int(run.get("id") or 0))


def latest_check_run_by_name(check_runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep the newest run per check name (same head SHA)."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in check_runs:
        if not isinstance(run, dict):
            continue
        name = str(run.get("name") or "").strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(run)
    return {name: max(runs, key=_run_sort_key) for name, runs in grouped.items()}


def latest_status_by_context(status_json: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(status_json, dict):
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in status_json.get("statuses") or []:
        if not isinstance(item, dict):
            continue
        ctx = str(item.get("context") or "").strip()
        if not ctx:
            continue
        grouped.setdefault(ctx, []).append(item)
    return {
        ctx: max(items, key=lambda s: str(s.get("updated_at") or ""))
        for ctx, items in grouped.items()
    }


def effective_ci_snapshot(
    status_json: dict[str, Any] | None,
    check_runs: list[dict[str, Any]],
    *,
    required: frozenset[str],
) -> dict[str, Any]:
    """Evaluate required checks using latest run per name (cancelled superseded by success)."""
    latest_runs = latest_check_run_by_name(check_runs)
    latest_status = latest_status_by_context(status_json)
    observed = observed_check_contexts(status_json, list(latest_runs.values()))
    missing = missing_required_contexts(required, observed)
    failing: list[str] = []
    pending: list[str] = []
    for ctx in sorted(required):
        run = latest_runs.get(ctx)
        if run:
            status = str(run.get("status") or "").lower()
            conclusion = str(run.get("conclusion") or "").lower()
            if status != "completed":
                pending.append(ctx)
            elif conclusion in FAIL_CONCLUSIONS:
                failing.append(ctx)
            continue
        stat = latest_status.get(ctx)
        if stat:
            state = str(stat.get("state") or "").lower()
            if state in ("pending", "expected", "queued"):
                pending.append(ctx)
            elif state in ("failure", "error"):
                failing.append(ctx)
            continue
        if ctx in missing:
            pending.append(ctx)
    raw_state = compute_raw_ci_state(status_json, list(latest_runs.values()), missing_required=missing)
    return {
        "missing_required": missing,
        "failing": failing,
        "pending": pending,
        "raw_ci_state": raw_state,
        "latest_runs": {name: {"conclusion": r.get("conclusion"), "status": r.get("status")} for name, r in latest_runs.items()},
    }


class _GhHttp:
    def __init__(self, client: GhClient) -> None:
        self._client = client

    def get(self, path: str, headers=None):
        endpoint = path.lstrip("/")
        body = self._client.api(endpoint)
        return 200, {}, body


def _fetch_pull(client: GhClient, repo: str, pr_number: int) -> dict[str, Any]:
    owner, name = _split_repo(repo)
    pull = client.api(f"repos/{owner}/{name}/pulls/{pr_number}")
    if not isinstance(pull, dict):
        raise GhApiError(f"pull request #{pr_number} missing")
    return pull


def _fetch_changed_files(client: GhClient, repo: str, pr_number: int) -> list[str]:
    owner, name = _split_repo(repo)
    paths: list[str] = []
    page = 1
    while True:
        batch = (
            client.api(
                f"repos/{owner}/{name}/pulls/{pr_number}/files",
                fields={"per_page": 100, "page": page},
            )
            or []
        )
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            if isinstance(item, dict):
                filename = item.get("filename")
                if filename:
                    paths.append(str(filename))
        if len(batch) < 100:
            break
        page += 1
    return paths


def _fetch_check_runs(client: GhClient, repo: str, head_sha: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    owner, name = _split_repo(repo)
    status_json = client.api(f"repos/{owner}/{name}/commits/{head_sha}/status") or {}
    if not isinstance(status_json, dict):
        status_json = {}
    check_runs: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = client.api(
            f"repos/{owner}/{name}/commits/{head_sha}/check-runs",
            fields={"per_page": 100, "page": page},
        )
        runs = payload.get("check_runs", []) if isinstance(payload, dict) else []
        if not isinstance(runs, list):
            break
        check_runs.extend(run for run in runs if isinstance(run, dict))
        if len(runs) < 100:
            break
        page += 1
    return status_json, check_runs


def run_unittest_discover(
    repo_root: str | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Run the PLATE unit test suite locally (stdlib unittest discover)."""
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    env = {"PYTHONPATH": "src"}
    run = runner or subprocess.run
    completed = run(
        cmd,
        cwd=repo_root or ".",
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"Ran (\d+) tests?", combined)
    count = int(match.group(1)) if match else None
    stale_warning = count is not None and count <= STALE_BASE_TEST_COUNT_WARN
    return {
        "exit_code": completed.returncode,
        "test_count": count,
        "stale_base_warning": stale_warning,
        "output_tail": combined[-2000:] if combined else "",
    }


def verify_pr(
    pr_number: int,
    repo: str | None = None,
    *,
    client: GhClient | None = None,
    run_tests: bool = False,
    repo_root: str | None = None,
    test_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Run mechanical pre-merge checks; return structured report."""
    target = resolve_repo(repo)
    owner, name = _split_repo(target)
    gh = client or GhClient()
    checks: list[VerifyCheck] = []

    pull = _fetch_pull(gh, target, pr_number)
    labels = _label_names(pull)
    type_matches = _pr_type_labels(labels)
    base_ref = ((pull.get("base") or {}).get("ref") or "").strip()
    head_sha = ((pull.get("head") or {}).get("sha") or "").strip()
    body = pull.get("body") or ""
    milestone = pull.get("milestone")
    has_no_issue = "no-issue" in labels

    if base_ref == "main":
        checks.append(VerifyCheck("base_branch", True, "Base branch is main."))
    elif base_ref == "release":
        checks.append(
            VerifyCheck(
                "base_branch",
                False,
                "Base branch is release; PLATE PRs must target main.",
                {"base_ref": base_ref},
            )
        )
    else:
        checks.append(
            VerifyCheck(
                "base_branch",
                False,
                f"Base branch must be main (found {base_ref!r}).",
                {"base_ref": base_ref},
            )
        )

    if len(type_matches) == 1:
        checks.append(
            VerifyCheck(
                "pr_type_label",
                True,
                f"Exactly one PR type label: {type_matches[0]}.",
            )
        )
    else:
        checks.append(
            VerifyCheck(
                "pr_type_label",
                False,
                f"Expected exactly one PR type label ({', '.join(PR_TYPE_LABELS)}); "
                f"found: {', '.join(type_matches) or '(none)'}.",
                {"labels": type_matches},
            )
        )

    pr_type = type_matches[0] if len(type_matches) == 1 else None
    area_labels = [label for label in labels if AREA_LABEL_RE.match(label)]
    if pr_type == "Feature":
        if area_labels:
            checks.append(
                VerifyCheck(
                    "area_label",
                    True,
                    f"Feature PR has area label(s): {', '.join(area_labels)}.",
                )
            )
        else:
            checks.append(
                VerifyCheck(
                    "area_label",
                    False,
                    "Feature PRs require at least one area:* label.",
                )
            )
        paths = _fetch_changed_files(gh, target, pr_number)
        fragment_paths = [p for p in paths if UNRELEASED_FRAGMENT_RE.match(p)]
        if fragment_paths:
            checks.append(
                VerifyCheck(
                    "release_fragment",
                    True,
                    "Unreleased release fragment present in PR files.",
                    {"paths": fragment_paths[:5]},
                )
            )
        else:
            checks.append(
                VerifyCheck(
                    "release_fragment",
                    False,
                    "Feature PRs require a JSON fragment under .agentic/releases/unreleased/.",
                )
            )
    elif pr_type:
        checks.append(
            VerifyCheck(
                "area_label",
                True,
                "area:* label not required for this PR type.",
                {"skipped": True},
            )
        )
        checks.append(
            VerifyCheck(
                "release_fragment",
                True,
                "Release fragment not required for this PR type.",
                {"skipped": True},
            )
        )

    if milestone or has_no_issue or pr_type == "Feedback Response":
        if milestone:
            checks.append(
                VerifyCheck(
                    "milestone",
                    True,
                    f"Milestone set: {milestone.get('title')}.",
                )
            )
        else:
            checks.append(
                VerifyCheck(
                    "milestone",
                    True,
                    "Milestone waived (no-issue or Feedback Response PR).",
                    {"waived": True},
                )
            )
    else:
        checks.append(
            VerifyCheck(
                "milestone",
                False,
                "PR has no milestone; assign one with gh pr edit --milestone.",
            )
        )

    needs_closing = pr_type in ("Bug", "Feature", "Documentation") and not has_no_issue and pr_type != "Feedback Response"
    if not needs_closing:
        checks.append(
            VerifyCheck(
                "closing_keyword",
                True,
                "Closing keyword not required for this PR.",
                {"waived": True},
            )
        )
    elif body_has_strict_closing_keyword(body, owner=owner, repo=name):
        checks.append(VerifyCheck("closing_keyword", True, "PR body includes Closes/Fixes/Resolves #N."))
    else:
        checks.append(
            VerifyCheck(
                "closing_keyword",
                False,
                "PR body must include Closes, Fixes, or Resolves #N for the linked issue.",
            )
        )

    pr_data = _load_pr_data(gh, target, pr_number)
    sync = _detect_base_branch_out_of_sync(pr_data)
    if sync.get("out_of_sync"):
        checks.append(
            VerifyCheck(
                "base_sync",
                False,
                f"Head branch is out of sync with base ({sync.get('state')}).",
                {"merge_state": sync.get("state")},
            )
        )
    else:
        checks.append(
            VerifyCheck(
                "base_sync",
                True,
                f"Head branch is up to date with base ({sync.get('state') or 'UNKNOWN'}).",
            )
        )

    ci_details: dict[str, Any] = {}
    if head_sha:
        status_json, check_runs = _fetch_check_runs(gh, target, head_sha)
        required = fetch_required_check_contexts(_GhHttp(gh), target, base_ref)
        if not required:
            required = frozenset(RECOMMENDED_REQUIRED_CHECK_CONTEXTS)
        ci_details = effective_ci_snapshot(status_json, check_runs, required=required)
        if ci_details["missing_required"]:
            checks.append(
                VerifyCheck(
                    "required_checks",
                    False,
                    "Required check contexts missing on head commit.",
                    ci_details,
                )
            )
        elif ci_details["pending"]:
            checks.append(
                VerifyCheck(
                    "required_checks",
                    False,
                    "Required checks still pending.",
                    ci_details,
                )
            )
        elif ci_details["failing"]:
            checks.append(
                VerifyCheck(
                    "required_checks",
                    False,
                    "One or more required checks are failing.",
                    ci_details,
                )
            )
        else:
            checks.append(
                VerifyCheck(
                    "required_checks",
                    True,
                    "Required checks present and green (latest run per context).",
                    ci_details,
                )
            )
    else:
        checks.append(
            VerifyCheck(
                "required_checks",
                False,
                "Could not resolve head SHA for CI inspection.",
            )
        )

    try:
        unresolved = get_unresolved_review_threads(pr_number, repo=target, client=gh)
        if unresolved:
            checks.append(
                VerifyCheck(
                    "review_threads",
                    False,
                    f"{len(unresolved)} unresolved review thread(s).",
                    {"count": len(unresolved)},
                )
            )
        else:
            checks.append(VerifyCheck("review_threads", True, "All review threads resolved."))
    except GhApiError as exc:
        if pr_data.get("review_threads_unavailable"):
            checks.append(
                VerifyCheck(
                    "review_threads",
                    False,
                    "Review thread data unavailable; cannot verify feedback resolution.",
                    {"error": str(exc)},
                )
            )
        else:
            checks.append(
                VerifyCheck(
                    "review_threads",
                    False,
                    f"Failed to load review threads: {exc}",
                )
            )

    test_report: dict[str, Any] | None = None
    if run_tests:
        test_report = run_unittest_discover(repo_root, runner=test_runner)
        passed = test_report.get("exit_code") == 0 and test_report.get("test_count") is not None
        msg = f"Local unittest discover: {test_report.get('test_count')} tests."
        if test_report.get("stale_base_warning"):
            msg += (
                f" Warning: count <= {STALE_BASE_TEST_COUNT_WARN} may indicate a stale base "
                "(expected ~1383 on current main)."
            )
        if not passed:
            msg += " Suite did not pass."
        checks.append(
            VerifyCheck(
                "local_tests",
                passed,
                msg,
                test_report,
            )
        )

    passed_all = all(item.passed for item in checks)
    return {
        "repo": target,
        "pr_number": pr_number,
        "passed": passed_all,
        "checks": [item.to_dict() for item in checks],
        "test_report": test_report,
    }


def format_pr_verify_text(report: dict[str, Any]) -> str:
    lines = [
        f"Repo: {report.get('repo')}",
        f"PR: #{report.get('pr_number')}",
        f"Overall: {'PASS' if report.get('passed') else 'FAIL'}",
        "",
    ]
    for check in report.get("checks") or []:
        status = "pass" if check.get("passed") else "FAIL"
        lines.append(f"[{status}] {check.get('id')}: {check.get('message')}")
    return "\n".join(lines)
