"""Tiered CI job selection by cost class and PR kind (#1332).

Builds on path-to-jobs selection (#1270) with policy from Design #1268 and Andrew's
2026-11-02 decisions on issue #1332. Does not change workflow required checks; adopters
wire this helper in a follow-up after owner approval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from plate_core.ci_path_jobs import (
    CiJobSelection,
    CiPathJobsError,
    _effective_all_jobs,
    _normalize_path,
    _path_matches_pattern,
    git_changed_paths,
    load_ci_path_jobs_config,
    select_ci_jobs,
    validate_ci_path_jobs_config,
)

DEFAULT_POLICY_RELATIVE = Path(".agentic") / "ci-policy.yml"
DEFAULT_POLICY_YAML_RELATIVE = Path(".agentic") / "ci-policy.yaml"

JobSize = Literal["small", "medium", "large"]
PrKind = Literal[
    "ordinary",
    "release_patch",
    "release_minor",
    "release_major",
    "nightly",
]

ALLOWED_JOB_SIZES = frozenset({"small", "medium", "large"})
ALLOWED_PR_KINDS = frozenset(
    {"ordinary", "release_patch", "release_minor", "release_major", "nightly"}
)

DEFAULT_COST_TIERS: dict[str, dict[str, float]] = {
    "small": {"max_usd": 0.10},
    "medium": {"min_usd": 0.10, "max_usd": 2.00},
    "large": {"min_usd": 2.00},
}

DEFAULT_FORCE_RUN: dict[str, Any] = {
    "workflow_globs": [".github/workflows/**"],
    "map_paths": [
        ".agentic/ci-path-jobs.yml",
        ".agentic/ci-path-jobs.yaml",
        ".agentic/ci-policy.yml",
        ".agentic/ci-policy.yaml",
    ],
    "test_path_globs": ["tests/**", "**/test_*.py", "**/*_test.py"],
    "on_workflow_change": "all_jobs",
    "on_map_change": "all_jobs",
}


class CiTieredPolicyError(ValueError):
    """Invalid tiered CI policy config or selection."""


@dataclass
class TieredSelectionMeta:
    pr_kind: str
    max_job_size: str | None
    forced_jobs: list[str]
    always_small_jobs: list[str]
    path_selected_jobs: list[str]
    tier_filtered_out: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_kind": self.pr_kind,
            "max_job_size": self.max_job_size,
            "forced_jobs": list(self.forced_jobs),
            "always_small_jobs": list(self.always_small_jobs),
            "path_selected_jobs": list(self.path_selected_jobs),
            "tier_filtered_out": list(self.tier_filtered_out),
        }


def _read_yaml_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CiTieredPolicyError(f"{path}: root must be a mapping")
    return data


def _plate_ci_policy(repo_root: Path) -> dict[str, Any] | None:
    plate_file = repo_root / ".plate"
    if not plate_file.is_file():
        return None
    try:
        data = json.loads(plate_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CiTieredPolicyError(f".plate is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        return None
    ci = data.get("ci")
    if not isinstance(ci, dict):
        return None
    nested = ci.get("policy")
    if nested is None:
        return None
    if not isinstance(nested, dict):
        raise CiTieredPolicyError("ci.policy in .plate must be an object")
    return nested


def default_policy_config() -> dict[str, Any]:
    return {
        "version": "1",
        "enabled": True,
        "cost_tiers": dict(DEFAULT_COST_TIERS),
        "job_sizes": {},
        "force_run": dict(DEFAULT_FORCE_RUN),
    }


def load_ci_tiered_policy_config(
    repo_root: Path | str | None = None,
    *,
    config_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    root = Path(repo_root or ".").resolve()
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise CiTieredPolicyError(f"policy config not found: {path}")
        return _read_yaml_file(path.resolve()), str(path.resolve())

    for candidate in (DEFAULT_POLICY_RELATIVE, DEFAULT_POLICY_YAML_RELATIVE):
        full = root / candidate
        if full.is_file():
            return _read_yaml_file(full), str(full)

    nested = _plate_ci_policy(root)
    if nested is not None:
        return nested, str(root / ".plate") + " (ci.policy)"

    return {"enabled": False}, ""


def _merge_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = default_policy_config()
    merged.update({k: v for k, v in config.items() if k != "cost_tiers" and k != "force_run"})
    cost = dict(DEFAULT_COST_TIERS)
    if isinstance(config.get("cost_tiers"), dict):
        for tier, bounds in config["cost_tiers"].items():
            if isinstance(bounds, dict):
                cost.setdefault(tier, {})
                cost[tier].update(bounds)
    merged["cost_tiers"] = cost
    force = dict(DEFAULT_FORCE_RUN)
    if isinstance(config.get("force_run"), dict):
        for key, val in config["force_run"].items():
            force[key] = val
    merged["force_run"] = force
    if isinstance(config.get("job_sizes"), dict):
        merged["job_sizes"] = dict(config["job_sizes"])
    return merged


def validate_ci_tiered_policy_config(
    config: dict[str, Any],
    *,
    path_jobs_config: dict[str, Any] | None = None,
) -> None:
    if not isinstance(config, dict):
        raise CiTieredPolicyError("policy config must be a mapping")

    merged = _merge_defaults(config)

    version = merged.get("version", "1")
    if not isinstance(version, str) or not version.strip():
        raise CiTieredPolicyError("version must be a non-empty string")

    enabled = merged.get("enabled", True)
    if not isinstance(enabled, bool):
        raise CiTieredPolicyError("enabled must be a boolean when present")

    cost_tiers = merged.get("cost_tiers") or {}
    if not isinstance(cost_tiers, dict):
        raise CiTieredPolicyError("cost_tiers must be a mapping")
    for tier in ("small", "medium", "large"):
        if tier not in cost_tiers:
            raise CiTieredPolicyError(f"cost_tiers must define {tier}")
        bounds = cost_tiers[tier]
        if not isinstance(bounds, dict):
            raise CiTieredPolicyError(f"cost_tiers.{tier} must be a mapping")
        for key in bounds:
            if key not in ("min_usd", "max_usd"):
                raise CiTieredPolicyError(f"cost_tiers.{tier} unknown key {key!r}")
            val = bounds[key]
            if not isinstance(val, (int, float)) or val < 0:
                raise CiTieredPolicyError(f"cost_tiers.{tier}.{key} must be a non-negative number")

    small_max = cost_tiers["small"].get("max_usd")
    medium_min = cost_tiers["medium"].get("min_usd")
    medium_max = cost_tiers["medium"].get("max_usd")
    large_min = cost_tiers["large"].get("min_usd")
    if small_max is not None and medium_min is not None and small_max > medium_min:
        raise CiTieredPolicyError("cost_tiers: small max_usd must be <= medium min_usd")
    if medium_max is not None and large_min is not None and medium_max > large_min:
        raise CiTieredPolicyError("cost_tiers: medium max_usd must be <= large min_usd")

    job_sizes = merged.get("job_sizes") or {}
    if not isinstance(job_sizes, dict):
        raise CiTieredPolicyError("job_sizes must be a mapping")
    for job_id, size in job_sizes.items():
        if not isinstance(job_id, str) or not job_id.strip():
            raise CiTieredPolicyError("job_sizes keys must be non-empty strings")
        if size not in ALLOWED_JOB_SIZES:
            raise CiTieredPolicyError(
                f"job_sizes[{job_id!r}] must be one of {sorted(ALLOWED_JOB_SIZES)}"
            )

    force_run = merged.get("force_run") or {}
    if not isinstance(force_run, dict):
        raise CiTieredPolicyError("force_run must be a mapping")
    for list_key in ("workflow_globs", "map_paths", "test_path_globs"):
        items = force_run.get(list_key, DEFAULT_FORCE_RUN.get(list_key, []))
        if items is not None and not isinstance(items, list):
            raise CiTieredPolicyError(f"force_run.{list_key} must be a list")
        for item in items or []:
            if not isinstance(item, str) or not item.strip():
                raise CiTieredPolicyError(f"force_run.{list_key} entries must be non-empty strings")

    for action_key in ("on_workflow_change", "on_map_change"):
        action = force_run.get(action_key, DEFAULT_FORCE_RUN.get(action_key))
        if action is None:
            continue
        if action == "all_jobs":
            continue
        if not isinstance(action, list):
            raise CiTieredPolicyError(
                f"force_run.{action_key} must be 'all_jobs' or a list of job ids"
            )
        for job in action:
            if not isinstance(job, str) or not job.strip():
                raise CiTieredPolicyError(
                    f"force_run.{action_key} job entries must be non-empty strings"
                )

    if path_jobs_config is not None:
        all_jobs = set(_effective_all_jobs(path_jobs_config))
        unknown = sorted(set(job_sizes) - all_jobs)
        if unknown:
            raise CiTieredPolicyError(
                "job_sizes references unknown job ids: " + ", ".join(unknown)
            )
        missing = sorted(all_jobs - set(job_sizes))
        if missing and enabled:
            raise CiTieredPolicyError(
                "job_sizes must classify every optional job id; missing: "
                + ", ".join(missing)
            )


def _size_rank(size: JobSize) -> int:
    return {"small": 0, "medium": 1, "large": 2}[size]


def max_job_size_for_kind(pr_kind: str) -> JobSize | None:
    if pr_kind not in ALLOWED_PR_KINDS:
        raise CiTieredPolicyError(
            f"pr_kind must be one of {sorted(ALLOWED_PR_KINDS)}; got {pr_kind!r}"
        )
    if pr_kind in ("release_major", "nightly"):
        return None
    if pr_kind in ("ordinary", "release_patch"):
        return "medium"
    if pr_kind == "release_minor":
        return "large"
    return "medium"


def _job_size(job_id: str, job_sizes: dict[str, JobSize]) -> JobSize:
    size = job_sizes.get(job_id)
    if size is None:
        raise CiTieredPolicyError(f"job_sizes missing entry for job {job_id!r}")
    return size  # type: ignore[return-value]


def _matches_any_glob(path: str, patterns: list[str]) -> bool:
    norm = _normalize_path(path)
    return any(_path_matches_pattern(p, norm) for p in patterns)


def _resolve_force_action(
    action: Any,
    all_jobs: list[str],
) -> list[str]:
    if action == "all_jobs" or action is None:
        return list(all_jobs)
    if isinstance(action, list):
        return list(action)
    return list(all_jobs)


def forced_jobs_for_changes(
    changed_paths: list[str],
    added_paths: list[str],
    *,
    path_jobs_config: dict[str, Any],
    policy_config: dict[str, Any],
) -> list[str]:
    """Return job ids that must run regardless of tier caps."""

    merged = _merge_defaults(policy_config)
    force = merged.get("force_run") or {}
    all_jobs = _effective_all_jobs(path_jobs_config)
    forced: list[str] = []
    seen: set[str] = set()

    def add_jobs(jobs: list[str]) -> None:
        for job in jobs:
            if job not in seen:
                seen.add(job)
                forced.append(job)

    workflow_globs = force.get("workflow_globs") or DEFAULT_FORCE_RUN["workflow_globs"]
    map_paths = force.get("map_paths") or DEFAULT_FORCE_RUN["map_paths"]
    test_globs = force.get("test_path_globs") or DEFAULT_FORCE_RUN["test_path_globs"]

    if any(_matches_any_glob(p, workflow_globs) for p in changed_paths):
        add_jobs(
            _resolve_force_action(force.get("on_workflow_change"), all_jobs)
        )

    if any(_matches_any_glob(p, map_paths) for p in changed_paths):
        add_jobs(_resolve_force_action(force.get("on_map_change"), all_jobs))

    added_tests = [
        p
        for p in added_paths
        if _matches_any_glob(p, test_globs)
    ]
    if added_tests:
        test_sel = select_ci_jobs(added_tests, path_jobs_config)
        add_jobs(test_sel.jobs_to_run if not test_sel.run_all else all_jobs)

    return forced


def select_tiered_ci_jobs(
    changed_paths: list[str],
    path_jobs_config: dict[str, Any],
    policy_config: dict[str, Any],
    *,
    pr_kind: str = "ordinary",
    added_paths: list[str] | None = None,
) -> tuple[CiJobSelection, TieredSelectionMeta]:
    """Select optional CI jobs using path map, tier caps, and force-run rules."""

    validate_ci_path_jobs_config(path_jobs_config)
    validate_ci_tiered_policy_config(
        policy_config, path_jobs_config=path_jobs_config
    )
    if pr_kind not in ALLOWED_PR_KINDS:
        raise CiTieredPolicyError(f"unknown pr_kind: {pr_kind!r}")

    merged_policy = _merge_defaults(policy_config)
    if not merged_policy.get("enabled", True):
        base = select_ci_jobs(changed_paths, path_jobs_config)
        meta = TieredSelectionMeta(
            pr_kind=pr_kind,
            max_job_size=max_job_size_for_kind(pr_kind),
            forced_jobs=[],
            always_small_jobs=[],
            path_selected_jobs=list(base.jobs_to_run),
            tier_filtered_out=[],
        )
        return base, meta

    job_sizes: dict[str, JobSize] = merged_policy.get("job_sizes") or {}
    all_jobs = _effective_all_jobs(path_jobs_config)
    normalized = [_normalize_path(p) for p in changed_paths if p and str(p).strip()]
    added = (
        [_normalize_path(p) for p in (added_paths or []) if p and str(p).strip()]
        if added_paths is not None
        else []
    )

    full_suite = pr_kind in ("release_major", "nightly")
    path_sel = select_ci_jobs(
        normalized,
        path_jobs_config,
        full_suite=full_suite,
    )

    max_size = max_job_size_for_kind(pr_kind)
    small_jobs = sorted(
        job for job in all_jobs if _job_size(job, job_sizes) == "small"
    )

    if path_sel.run_all:
        path_jobs = list(all_jobs)
    else:
        path_jobs = list(path_sel.jobs_to_run)

    forced = forced_jobs_for_changes(
        normalized,
        added,
        path_jobs_config=path_jobs_config,
        policy_config=policy_config,
    )

    candidates: list[str] = []
    seen: set[str] = set()
    for job in small_jobs + path_jobs + forced:
        if job not in seen:
            seen.add(job)
            candidates.append(job)

    tier_filtered_out: list[str] = []
    if max_size is None:
        jobs_to_run = list(all_jobs)
        run_all = True
    else:
        run_all = False
        max_rank = _size_rank(max_size)
        jobs_to_run = []
        for job in candidates:
            if _size_rank(_job_size(job, job_sizes)) <= max_rank:
                jobs_to_run.append(job)
            else:
                tier_filtered_out.append(job)
        for job in forced:
            if job not in jobs_to_run:
                jobs_to_run.append(job)
            if job in tier_filtered_out:
                tier_filtered_out.remove(job)
        run_all = set(jobs_to_run) == set(all_jobs) and len(all_jobs) > 0

    skip = [j for j in all_jobs if j not in set(jobs_to_run)]

    selection = CiJobSelection(
        enabled=True,
        run_all=run_all,
        jobs_to_run=jobs_to_run,
        jobs_to_skip=skip,
        matched_modules=path_sel.matched_modules,
        changed_paths=normalized,
        unmatched_paths=path_sel.unmatched_paths,
        safety=path_sel.safety,
        reason=path_sel.reason or f"tiered selection pr_kind={pr_kind}",
        full_suite=full_suite,
    )

    meta = TieredSelectionMeta(
        pr_kind=pr_kind,
        max_job_size=max_size,
        forced_jobs=forced,
        always_small_jobs=small_jobs,
        path_selected_jobs=path_jobs,
        tier_filtered_out=sorted(set(tier_filtered_out) - set(forced)),
    )
    return selection, meta


def git_added_paths(
    repo_root: Path | str,
    *,
    base_ref: str,
    head_ref: str = "HEAD",
) -> list[str]:
    """Paths added between base and head (diff-filter=A)."""

    root = Path(repo_root).resolve()
    cmd = [
        "git",
        "diff",
        "--name-status",
        "--diff-filter=A",
        "-M",
        f"{base_ref}...{head_ref}",
    ]
    import subprocess

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CiPathJobsError(
            f"git diff failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    from plate_core.ci_path_jobs import _paths_from_name_status_output

    return _paths_from_name_status_output(proc.stdout)


def tiered_selection_for_repo(
    repo_root: Path | str,
    *,
    changed_paths: list[str] | None = None,
    added_paths: list[str] | None = None,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    path_jobs_config_path: Path | str | None = None,
    policy_config_path: Path | str | None = None,
    pr_kind: str = "ordinary",
    full_suite: bool = False,
) -> tuple[CiJobSelection, TieredSelectionMeta]:
    root = Path(repo_root).resolve()
    path_cfg, _ = load_ci_path_jobs_config(root, config_path=path_jobs_config_path)
    policy_cfg, _ = load_ci_tiered_policy_config(root, config_path=policy_config_path)

    if full_suite or pr_kind == "nightly":
        pr_kind = "nightly"

    if changed_paths is not None:
        paths = list(changed_paths)
    elif base_ref:
        paths = git_changed_paths(root, base_ref=base_ref, head_ref=head_ref)
    else:
        paths = []

    if added_paths is not None:
        added = list(added_paths)
    elif base_ref:
        added = git_added_paths(root, base_ref=base_ref, head_ref=head_ref)
    else:
        added = []

    if not paths and not base_ref and bool(path_cfg.get("enabled", True)):
        fail_sel = CiJobSelection(
            enabled=True,
            run_all=False,
            jobs_to_run=[],
            jobs_to_skip=_effective_all_jobs(path_cfg),
            matched_modules=[],
            changed_paths=[],
            unmatched_paths=[],
            safety="fail",
            reason="no change source: provide changed_paths or base_ref",
        )
        meta = TieredSelectionMeta(
            pr_kind=pr_kind,
            max_job_size=max_job_size_for_kind(pr_kind),
            forced_jobs=[],
            always_small_jobs=[],
            path_selected_jobs=[],
            tier_filtered_out=[],
        )
        return fail_sel, meta

    return select_tiered_ci_jobs(
        paths,
        path_cfg,
        policy_cfg,
        pr_kind=pr_kind,
        added_paths=added,
    )
