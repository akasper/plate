"""Path-to-CI-jobs map loading and changed-path selection (#1270).

Adopters declare modules, path globs, and job ids in ``.agentic/ci-path-jobs.yml``
(or ``ci.path_jobs`` inside ``.plate``). A helper selects which optional CI jobs
to run for a pull request while keeping required contexts ``labels``, ``test``, and
``pr-gates`` satisfied via aggregate/skip patterns documented for workflows.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

DEFAULT_CONFIG_RELATIVE = Path(".agentic") / "ci-path-jobs.yml"
DEFAULT_CONFIG_YAML_RELATIVE = Path(".agentic") / "ci-path-jobs.yaml"

UnmatchedPolicy = Literal["run_all", "fail"]
EmptySelectionPolicy = Literal["run_all", "fail"]

ALLOWED_UNMATCHED = frozenset({"run_all", "fail"})
ALLOWED_EMPTY = frozenset({"run_all", "fail"})


class CiPathJobsError(ValueError):
    """Invalid config or unsafe selection."""


@dataclass
class CiJobSelection:
    enabled: bool
    run_all: bool
    jobs_to_run: list[str]
    jobs_to_skip: list[str]
    matched_modules: list[str]
    changed_paths: list[str]
    unmatched_paths: list[str]
    safety: str
    reason: str = ""
    full_suite: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_path(path: str) -> str:
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _path_matches_pattern(pattern: str, path: str) -> bool:
    pattern = _normalize_path(pattern)
    path = _normalize_path(path)
    if not pattern:
        return False
    if pattern.endswith("/**"):
        base = pattern[:-3].rstrip("/")
        return path == base or path.startswith(base + "/")
    if pattern.endswith("/**/"):
        base = pattern[:-4].rstrip("/")
        return path == base or path.startswith(base + "/")
    if pattern.endswith("/"):
        base = pattern.rstrip("/")
        return path == base or path.startswith(base + "/")
    if fnmatch.fnmatch(path, pattern):
        return True
    # Allow directory-style patterns without trailing slash
    if "/" not in pattern and fnmatch.fnmatch(Path(path).name, pattern):
        return True
    return False


def _read_yaml_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CiPathJobsError(f"{path}: root must be a mapping")
    return data


def _plate_ci_path_jobs(repo_root: Path) -> dict[str, Any] | None:
    plate_file = repo_root / ".plate"
    if not plate_file.is_file():
        return None
    try:
        data = json.loads(plate_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CiPathJobsError(f".plate is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        return None
    ci = data.get("ci")
    if not isinstance(ci, dict):
        return None
    nested = ci.get("path_jobs")
    if nested is None:
        return None
    if not isinstance(nested, dict):
        raise CiPathJobsError("ci.path_jobs in .plate must be an object")
    return nested


def load_ci_path_jobs_config(
    repo_root: Path | str | None = None,
    *,
    config_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Load path-jobs config from explicit path, .agentic file, or .plate ci.path_jobs."""

    root = Path(repo_root or ".").resolve()
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            raise CiPathJobsError(f"config not found: {path}")
        return _read_yaml_file(path.resolve()), str(path.resolve())

    for candidate in (DEFAULT_CONFIG_RELATIVE, DEFAULT_CONFIG_YAML_RELATIVE):
        full = root / candidate
        if full.is_file():
            return _read_yaml_file(full), str(full)

    nested = _plate_ci_path_jobs(root)
    if nested is not None:
        return nested, str(root / ".plate") + " (ci.path_jobs)"

    return {"enabled": False}, ""


def validate_ci_path_jobs_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise CiPathJobsError("config must be a mapping")

    version = config.get("version", "1")
    if not isinstance(version, str) or not version.strip():
        raise CiPathJobsError("version must be a non-empty string")

    enabled = config.get("enabled", True)
    if not isinstance(enabled, bool):
        raise CiPathJobsError("enabled must be a boolean when present")

    unmatched = config.get("unmatched_paths", "run_all")
    if unmatched not in ALLOWED_UNMATCHED:
        raise CiPathJobsError(f"unmatched_paths must be one of {sorted(ALLOWED_UNMATCHED)}")

    empty_sel = config.get("empty_selection", "run_all")
    if empty_sel not in ALLOWED_EMPTY:
        raise CiPathJobsError(f"empty_selection must be one of {sorted(ALLOWED_EMPTY)}")

    all_jobs = config.get("all_jobs", [])
    if all_jobs is not None and not isinstance(all_jobs, list):
        raise CiPathJobsError("all_jobs must be a list when present")
    for job in all_jobs or []:
        if not isinstance(job, str) or not job.strip():
            raise CiPathJobsError("all_jobs entries must be non-empty strings")

    modules = config.get("modules", {})
    if not isinstance(modules, dict):
        raise CiPathJobsError("modules must be a mapping")

    seen_ids: set[str] = set()
    for module_id, spec in modules.items():
        if not isinstance(module_id, str) or not module_id.strip():
            raise CiPathJobsError("module ids must be non-empty strings")
        if module_id in seen_ids:
            raise CiPathJobsError(f"duplicate module id: {module_id}")
        seen_ids.add(module_id)
        if not isinstance(spec, dict):
            raise CiPathJobsError(f"module {module_id!r} must be a mapping")
        paths = spec.get("paths", [])
        if not isinstance(paths, list) or not paths:
            raise CiPathJobsError(f"module {module_id!r} requires a non-empty paths list")
        for p in paths:
            if not isinstance(p, str) or not p.strip():
                raise CiPathJobsError(f"module {module_id!r} paths must be non-empty strings")
        jobs = spec.get("jobs", [])
        if not isinstance(jobs, list) or not jobs:
            raise CiPathJobsError(f"module {module_id!r} requires a non-empty jobs list")
        for j in jobs:
            if not isinstance(j, str) or not j.strip():
                raise CiPathJobsError(f"module {module_id!r} jobs must be non-empty strings")
        iface = spec.get("interface", False)
        if not isinstance(iface, bool):
            raise CiPathJobsError(f"module {module_id!r} interface must be boolean")
        depends_on = spec.get("depends_on", [])
        if depends_on is not None and not isinstance(depends_on, list):
            raise CiPathJobsError(f"module {module_id!r} depends_on must be a list")
        for dep in depends_on or []:
            if not isinstance(dep, str) or not dep.strip():
                raise CiPathJobsError(f"module {module_id!r} depends_on entries must be strings")

    for module_id, spec in modules.items():
        for dep in spec.get("depends_on") or []:
            if dep not in modules:
                raise CiPathJobsError(f"module {module_id!r} depends_on unknown module {dep!r}")


def _modules_triggered_by_paths(
    changed_paths: list[str],
    modules: dict[str, Any],
) -> tuple[set[str], list[str]]:
    """Return module ids activated directly or via interface dependents."""

    direct: set[str] = set()
    unmatched: list[str] = []

    for path in changed_paths:
        norm = _normalize_path(path)
        matched_any = False
        for module_id, spec in modules.items():
            for pattern in spec.get("paths") or []:
                if _path_matches_pattern(str(pattern), norm):
                    direct.add(module_id)
                    matched_any = True
                    break
        if not matched_any:
            unmatched.append(norm)

    activated = set(direct)
    # Interface modules: when touched, also run jobs for modules that depend on them.
    for module_id in list(direct):
        spec = modules.get(module_id) or {}
        if not spec.get("interface"):
            continue
        for other_id, other in modules.items():
            deps = other.get("depends_on") or []
            if module_id in deps:
                activated.add(other_id)

    return activated, unmatched


def select_ci_jobs(
    changed_paths: list[str],
    config: dict[str, Any],
    *,
    full_suite: bool = False,
) -> CiJobSelection:
    """Select CI job ids for the given changed paths."""

    validate_ci_path_jobs_config(config)
    normalized = [_normalize_path(p) for p in changed_paths if p and str(p).strip()]
    enabled = bool(config.get("enabled", True))

    all_jobs: list[str] = list(config.get("all_jobs") or [])
    if not all_jobs:
        # Derive union of module jobs when all_jobs omitted
        modules_cfg = config.get("modules") or {}
        derived: list[str] = []
        seen: set[str] = set()
        for spec in modules_cfg.values():
            for j in spec.get("jobs") or []:
                if j not in seen:
                    seen.add(j)
                    derived.append(j)
        all_jobs = derived

    if not enabled or full_suite or _env_truthy("PLATE_CI_FULL_SUITE"):
        return CiJobSelection(
            enabled=enabled,
            run_all=True,
            jobs_to_run=list(all_jobs),
            jobs_to_skip=[],
            matched_modules=[],
            changed_paths=normalized,
            unmatched_paths=[],
            safety="ok",
            reason="selection disabled or full suite requested",
            full_suite=full_suite or _env_truthy("PLATE_CI_FULL_SUITE"),
        )

    modules: dict[str, Any] = config.get("modules") or {}
    if not modules:
        return CiJobSelection(
            enabled=True,
            run_all=True,
            jobs_to_run=list(all_jobs),
            jobs_to_skip=[],
            matched_modules=[],
            changed_paths=normalized,
            unmatched_paths=[],
            safety="ok",
            reason="no modules configured",
        )

    if not normalized:
        return CiJobSelection(
            enabled=True,
            run_all=False,
            jobs_to_run=[],
            jobs_to_skip=list(all_jobs),
            matched_modules=[],
            changed_paths=[],
            unmatched_paths=[],
            safety="ok",
            reason="no changed paths",
        )

    activated, unmatched = _modules_triggered_by_paths(normalized, modules)
    unmatched_policy: UnmatchedPolicy = config.get("unmatched_paths", "run_all")
    empty_policy: EmptySelectionPolicy = config.get("empty_selection", "run_all")

    if unmatched and unmatched_policy == "fail":
        return CiJobSelection(
            enabled=True,
            run_all=False,
            jobs_to_run=[],
            jobs_to_skip=list(all_jobs),
            matched_modules=sorted(activated),
            changed_paths=normalized,
            unmatched_paths=unmatched,
            safety="fail",
            reason=f"changed paths not covered by any module: {', '.join(unmatched)}",
        )

    if unmatched and unmatched_policy == "run_all":
        return CiJobSelection(
            enabled=True,
            run_all=True,
            jobs_to_run=list(all_jobs),
            jobs_to_skip=[],
            matched_modules=sorted(activated),
            changed_paths=normalized,
            unmatched_paths=unmatched,
            safety="ok",
            reason="unmatched paths triggered run_all fallback",
        )

    jobs_to_run: list[str] = []
    seen_jobs: set[str] = set()
    for module_id in sorted(activated):
        spec = modules[module_id]
        for job in spec.get("jobs") or []:
            if job not in seen_jobs:
                seen_jobs.add(job)
                jobs_to_run.append(job)

    if not jobs_to_run and normalized:
        if empty_policy == "fail":
            return CiJobSelection(
                enabled=True,
                run_all=False,
                jobs_to_run=[],
                jobs_to_skip=list(all_jobs),
                matched_modules=sorted(activated),
                changed_paths=normalized,
                unmatched_paths=unmatched,
                safety="fail",
                reason="empty job selection with non-empty changes",
            )
        return CiJobSelection(
            enabled=True,
            run_all=True,
            jobs_to_run=list(all_jobs),
            jobs_to_skip=[],
            matched_modules=sorted(activated),
            changed_paths=normalized,
            unmatched_paths=unmatched,
            safety="ok",
            reason="empty_selection run_all fallback",
        )

    skip = [j for j in all_jobs if j not in set(jobs_to_run)]
    return CiJobSelection(
        enabled=True,
        run_all=False,
        jobs_to_run=jobs_to_run,
        jobs_to_skip=skip,
        matched_modules=sorted(activated),
        changed_paths=normalized,
        unmatched_paths=unmatched,
        safety="ok",
    )


def _env_truthy(name: str) -> bool:
    val = os.environ.get(name, "")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def git_changed_paths(
    repo_root: Path | str,
    *,
    base_ref: str,
    head_ref: str = "HEAD",
) -> list[str]:
    """Return paths changed between base and head using git (stdlib subprocess)."""

    root = Path(repo_root).resolve()
    cmd = [
        "git",
        "diff",
        "--name-only",
        f"{base_ref}...{head_ref}",
    ]
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
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return lines


def selection_for_repo(
    repo_root: Path | str,
    changed_paths: list[str] | None = None,
    *,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    config_path: Path | str | None = None,
    full_suite: bool = False,
) -> CiJobSelection:
    root = Path(repo_root).resolve()
    config, _src = load_ci_path_jobs_config(root, config_path=config_path)
    paths = list(changed_paths or [])
    if not paths and base_ref:
        paths = git_changed_paths(root, base_ref=base_ref, head_ref=head_ref)
    return select_ci_jobs(paths, config, full_suite=full_suite)


def format_github_outputs(selection: CiJobSelection) -> dict[str, str]:
    """Key/value strings suitable for GITHUB_OUTPUT."""

    jobs = selection.jobs_to_run if not selection.run_all else selection.jobs_to_run
    return {
        "run_all": "true" if selection.run_all else "false",
        "safety": selection.safety,
        "jobs_json": json.dumps(jobs),
        "jobs_csv": ",".join(jobs),
        "reason": selection.reason or "",
    }


def assert_selection_safe_for_merge(selection: CiJobSelection) -> None:
    """Fail closed when selection would hide changes (green skip of all jobs)."""

    if selection.safety == "fail":
        raise CiPathJobsError(selection.reason or "unsafe CI job selection")
    if selection.changed_paths and not selection.run_all and not selection.jobs_to_run:
        raise CiPathJobsError(
            "selection would skip every job while paths changed; use run_all fallback or fail policy"
        )
