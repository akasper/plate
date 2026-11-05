"""Local PR preflight before ``gh pr create`` (#1418)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from .health import resolve_repo
from .pr_gates_checks import (
    GateFailure,
    normalize_label_list,
    preflight_report_dict,
    resolve_expected_integration_base,
    run_preflight_gate_checks,
)
from .procutil import run_hidden
from .release import get_release_status


def _split_repo(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name


def parse_labels_option(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def collect_labels_from_argv(argv: list[str]) -> list[str]:
    labels: list[str] = []
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token in ("--label", "-l") and idx + 1 < len(argv):
            labels.append(argv[idx + 1])
            idx += 2
            continue
        if token.startswith("--label="):
            labels.append(token.split("=", 1)[1])
        elif token.startswith("--labels="):
            labels.extend(parse_labels_option(token.split("=", 1)[1]))
        idx += 1
    return labels


def read_body_from_argv(argv: list[str], repo_root: Path) -> str:
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token == "--body" and idx + 1 < len(argv):
            return argv[idx + 1]
        if token.startswith("--body="):
            return token.split("=", 1)[1]
        if token == "--body-file" and idx + 1 < len(argv):
            path = Path(argv[idx + 1])
            if not path.is_absolute():
                path = repo_root / path
            return path.read_text(encoding="utf-8")
        if token.startswith("--body-file="):
            path = Path(token.split("=", 1)[1])
            if not path.is_absolute():
                path = repo_root / path
            return path.read_text(encoding="utf-8")
        idx += 1
    return ""


def read_base_from_argv(argv: list[str]) -> str | None:
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token == "--base" and idx + 1 < len(argv):
            return argv[idx + 1]
        if token.startswith("--base="):
            return token.split("=", 1)[1]
        idx += 1
    return None


def git_changed_paths(
    repo_root: Path,
    base_branch: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_hidden,
) -> list[str]:
    """Paths changed on HEAD vs merge-base with ``origin/<base_branch>`` (includes staged)."""
    root = repo_root.resolve()
    ref = f"origin/{base_branch}"
    merge_base = runner(
        ["git", "-C", str(root), "merge-base", "HEAD", ref],
        capture_output=True,
        text=True,
    )
    if merge_base.returncode != 0:
        merge_base = runner(
            ["git", "-C", str(root), "merge-base", "HEAD", base_branch],
            capture_output=True,
            text=True,
        )
    base_sha = (merge_base.stdout or "").strip()
    paths: list[str] = []
    if base_sha:
        diff = runner(
            ["git", "-C", str(root), "diff", "--name-only", base_sha, "HEAD"],
            capture_output=True,
            text=True,
        )
        if diff.returncode == 0:
            paths.extend(line.strip() for line in (diff.stdout or "").splitlines() if line.strip())
    staged = runner(
        ["git", "-C", str(root), "diff", "--name-only", "--cached"],
        capture_output=True,
        text=True,
    )
    if staged.returncode == 0:
        paths.extend(line.strip() for line in (staged.stdout or "").splitlines() if line.strip())
    untracked = runner(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    if untracked.returncode == 0:
        paths.extend(line.strip() for line in (untracked.stdout or "").splitlines() if line.strip())
    # preserve order, dedupe
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def run_preflight(
    *,
    body: str | None = None,
    labels: list[str] | None = None,
    base: str | None = None,
    repo: str | None = None,
    repo_root: str | Path = ".",
    argv: list[str] | None = None,
    release_status: dict[str, Any] | None = None,
    changed_paths: list[str] | None = None,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    argv = list(argv or [])
    label_list = normalize_label_list(labels) or collect_labels_from_argv(argv)
    body_text = body if body is not None else read_body_from_argv(argv, root)
    base_ref = base if base is not None else read_base_from_argv(argv)

    target = resolve_repo(repo)
    owner, name = _split_repo(target)

    if release_status is None:
        report = get_release_status(repo)
        release_status = report.to_dict()

    mode = str(release_status.get("release_branch_mode") or "legacy")
    tracks = release_status.get("release_track_branches") or {}
    expected = resolve_expected_integration_base(
        release_branch_mode=mode,
        release_track_branches=tracks if isinstance(tracks, dict) else {},
        pr_labels=label_list,
    )
    compare_base = base_ref or expected
    paths = changed_paths
    if paths is None:
        runner = git_runner or run_hidden
        paths = git_changed_paths(root, compare_base, runner=runner)

    failures = run_preflight_gate_checks(
        body=body_text,
        labels=label_list,
        base=base_ref,
        changed_paths=paths,
        owner=owner,
        repo=name,
        release_branch_mode=mode,
        release_track_branches=tracks if isinstance(tracks, dict) else {},
    )
    return preflight_report_dict(failures, expected_base=expected, labels=label_list)


def format_preflight_text(report: dict[str, Any]) -> str:
    if report.get("passed"):
        return "PR preflight passed."
    lines = [str(item.get("message") or "") for item in report.get("failures") or []]
    return "\n".join(line for line in lines if line)


def format_preflight_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"


def create_pr_with_preflight(
    argv: list[str],
    *,
    repo_root: str | Path = ".",
    repo: str | None = None,
    gh_runner: Callable[..., subprocess.CompletedProcess[Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Run preflight, then ``gh pr create`` with the same argv when passing."""
    report = run_preflight(argv=argv, repo=repo, repo_root=repo_root)
    if not report.get("passed"):
        return 1, report
    runner = gh_runner or run_hidden
    cmd = ["gh", "pr", "create", *argv]
    completed = runner(cmd)
    report = dict(report)
    report["gh_exit_code"] = completed.returncode
    return (0 if completed.returncode == 0 else completed.returncode), report
