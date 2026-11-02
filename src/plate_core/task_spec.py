"""Validate `.agentic/tasks/*.yml` against the shipped task spec schema (#1333)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .baseline_catalog import load_baseline_catalog
from .mcp.tool_profiles import KNOWN_PROFILES, list_mcp_tool_names, tools_for_named_profiles

TASK_SPEC_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).resolve().parent / "data" / "task_spec.schema.json"

ISSUE_KINDS = frozenset(
    {
        "Bug",
        "Feature",
        "Epic",
        "Release",
        "Research",
        "Design",
        "Question",
        "Task",
        "Audit",
        "Migration",
        "Documentation",
        "Feedback Response",
    }
)

LEVELS = frozenset({"junior", "senior", "staff"})
ROUTES = frozenset({"docs", "tests", "fix", "feature", "review"})
TIERS = frozenset({"T0", "T1", "T2", "T3"})
TIER_ORDER = ("T0", "T1", "T2", "T3")
TYPED_FIELD_TYPES = frozenset(
    {
        "string",
        "text",
        "integer",
        "boolean",
        "issue_ref",
        "pr_ref",
        "file_path",
        "artifact_ref",
    }
)
APPROVAL_GATES = frozenset(
    {"none", "human-t3", "human-merge", "human-release", "human-external"}
)
NEXT_WHEN = frozenset({"success", "failure", "always"})

_ID_RE = __import__("re").compile(r"^[a-z][a-z0-9-]*$")
_FIELD_ID_RE = __import__("re").compile(r"^[a-z][a-z0-9_]*$")


class TaskSpecError(ValueError):
    """Raised when a task spec document is invalid."""


@dataclass(frozen=True)
class TaskSpecValidationReport:
    path: str
    task_id: str
    valid: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "task_id": self.task_id,
            "valid": self.valid,
            "errors": list(self.errors),
        }


def task_spec_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_task_spec_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TaskSpecError(f"{path}: root must be a mapping")
    return data


def _err(path: str, message: str) -> str:
    return f"{path}: {message}"


def _require_str(value: Any, field: str, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskSpecError(_err(path, f"{field} must be a non-empty string"))
    return value.strip()


def _validate_typed_fields(items: Any, field: str, path: str) -> None:
    if not isinstance(items, list):
        raise TaskSpecError(_err(path, f"{field} must be a list"))
    seen: set[str] = set()
    for index, item in enumerate(items):
        loc = f"{field}[{index}]"
        if not isinstance(item, dict):
            raise TaskSpecError(_err(path, f"{loc} must be a mapping"))
        fid = item.get("id")
        if not isinstance(fid, str) or not _FIELD_ID_RE.match(fid):
            raise TaskSpecError(_err(path, f"{loc}.id must match [a-z][a-z0-9_]*"))
        if fid in seen:
            raise TaskSpecError(_err(path, f"duplicate {field} id {fid!r}"))
        seen.add(fid)
        ftype = item.get("type")
        if ftype not in TYPED_FIELD_TYPES:
            raise TaskSpecError(
                _err(path, f"{loc}.type must be one of {sorted(TYPED_FIELD_TYPES)}")
            )
        if "required" in item and not isinstance(item["required"], bool):
            raise TaskSpecError(_err(path, f"{loc}.required must be a boolean when set"))
        if "description" in item and not isinstance(item["description"], str):
            raise TaskSpecError(_err(path, f"{loc}.description must be a string when set"))


def _validate_tools(tools: Any, path: str) -> None:
    if not isinstance(tools, dict):
        raise TaskSpecError(_err(path, "tools must be a mapping"))
    extra = set(tools) - {"allow", "profiles"}
    if extra:
        raise TaskSpecError(_err(path, f"tools has unknown keys: {sorted(extra)}"))
    allow = tools.get("allow", [])
    profiles = tools.get("profiles", [])
    if not isinstance(allow, list):
        raise TaskSpecError(_err(path, "tools.allow must be a list"))
    if not isinstance(profiles, list):
        raise TaskSpecError(_err(path, "tools.profiles must be a list"))
    if not allow and not profiles:
        raise TaskSpecError(_err(path, "tools must include allow and/or profiles"))
    known_tools = list_mcp_tool_names()
    for index, name in enumerate(allow):
        if not isinstance(name, str) or not name:
            raise TaskSpecError(_err(path, f"tools.allow[{index}] must be a non-empty string"))
        if name not in known_tools:
            raise TaskSpecError(_err(path, f"tools.allow[{index}] unknown MCP tool {name!r}"))
    for index, profile in enumerate(profiles):
        if not isinstance(profile, str) or not profile:
            raise TaskSpecError(_err(path, f"tools.profiles[{index}] must be a non-empty string"))
        key = profile.strip().lower()
        if key not in KNOWN_PROFILES:
            raise TaskSpecError(
                _err(
                    path,
                    f"tools.profiles[{index}] unknown profile {profile!r}; "
                    f"known: {', '.join(sorted(KNOWN_PROFILES))}",
                )
            )
        try:
            tools_for_named_profiles([key])
        except ValueError as exc:
            raise TaskSpecError(_err(path, str(exc))) from exc


def _validate_model_policy(model_policy: Any, path: str, approval: str) -> None:
    if not isinstance(model_policy, dict):
        raise TaskSpecError(_err(path, "model_policy must be a mapping"))
    allowed_keys = {"tiers", "start_tier", "escalation", "max_cost_usd", "t3_requires_approval"}
    extra = set(model_policy) - allowed_keys
    if extra:
        raise TaskSpecError(_err(path, f"model_policy has unknown keys: {sorted(extra)}"))
    tiers_raw = model_policy.get("tiers")
    if not isinstance(tiers_raw, list) or not tiers_raw:
        raise TaskSpecError(_err(path, "model_policy.tiers must be a non-empty list"))
    tiers: list[str] = []
    for index, tier in enumerate(tiers_raw):
        if tier not in TIERS:
            raise TaskSpecError(_err(path, f"model_policy.tiers[{index}] must be T0..T3"))
        if tier in tiers:
            raise TaskSpecError(_err(path, f"model_policy.tiers contains duplicate {tier}"))
        tiers.append(tier)
    start = model_policy.get("start_tier")
    if start not in TIERS:
        raise TaskSpecError(_err(path, "model_policy.start_tier must be T0..T3"))
    if start not in tiers:
        raise TaskSpecError(_err(path, "model_policy.start_tier must appear in model_policy.tiers"))
    max_cost = model_policy.get("max_cost_usd")
    if not isinstance(max_cost, (int, float)) or max_cost < 0:
        raise TaskSpecError(_err(path, "model_policy.max_cost_usd must be a number >= 0"))
    escalation = model_policy.get("escalation")
    if escalation is not None:
        if not isinstance(escalation, dict):
            raise TaskSpecError(_err(path, "model_policy.escalation must be a mapping"))
        if set(escalation) != {"from", "to"}:
            raise TaskSpecError(_err(path, "model_policy.escalation must have from and to only"))
        from_tier = escalation.get("from")
        to_tier = escalation.get("to")
        if from_tier not in TIERS or to_tier not in TIERS:
            raise TaskSpecError(_err(path, "model_policy.escalation from/to must be T0..T3"))
        if from_tier not in tiers or to_tier not in tiers:
            raise TaskSpecError(_err(path, "model_policy.escalation tiers must be listed in tiers"))
        if TIER_ORDER.index(to_tier) <= TIER_ORDER.index(from_tier):
            raise TaskSpecError(_err(path, "model_policy.escalation must move to a higher tier"))
    if "T3" in tiers:
        if model_policy.get("t3_requires_approval") != "human":
            raise TaskSpecError(
                _err(path, "model_policy.t3_requires_approval must be 'human' when T3 is allowed")
            )
        if approval not in ("human-t3", "human-merge", "human-release", "human-external"):
            raise TaskSpecError(
                _err(path, "approval must gate T3 (human-t3 or stronger) when T3 is allowed")
            )


def _validate_next(next_edges: Any, path: str, *, known_ids: frozenset[str] | None) -> None:
    if not isinstance(next_edges, list):
        raise TaskSpecError(_err(path, "next must be a list"))
    for index, edge in enumerate(next_edges):
        loc = f"next[{index}]"
        if not isinstance(edge, dict):
            raise TaskSpecError(_err(path, f"{loc} must be a mapping"))
        if set(edge) - {"task_id", "when"}:
            raise TaskSpecError(_err(path, f"{loc} has unknown keys"))
        task_id = edge.get("task_id")
        if not isinstance(task_id, str) or not _ID_RE.match(task_id):
            raise TaskSpecError(_err(path, f"{loc}.task_id must match [a-z][a-z0-9-]*"))
        when = edge.get("when", "success")
        if when not in NEXT_WHEN:
            raise TaskSpecError(_err(path, f"{loc}.when must be success, failure, or always"))
        if known_ids is not None and task_id not in known_ids:
            raise TaskSpecError(_err(path, f"{loc}.task_id references unknown task {task_id!r}"))


def validate_task_spec_document(
    data: dict[str, Any],
    *,
    path: str = "<document>",
    known_task_ids: frozenset[str] | None = None,
) -> TaskSpecValidationReport:
    errors: list[str] = []
    task_id = str(data.get("id") or "")

    try:
        version = data.get("task_spec_version")
        if version != TASK_SPEC_VERSION:
            raise TaskSpecError(
                _err(path, f"task_spec_version must be {TASK_SPEC_VERSION!r}, got {version!r}")
            )
        task_id = _require_str(data.get("id"), "id", path)
        if not _ID_RE.match(task_id):
            raise TaskSpecError(_err(path, "id must match [a-z][a-z0-9-]*"))
        role = _require_str(data.get("role"), "role", path)
        try:
            load_baseline_catalog().agent_by_id(role)
        except Exception as exc:
            raise TaskSpecError(_err(path, f"role {role!r} is not a baseline_catalog agent id")) from exc
        kind = _require_str(data.get("kind"), "kind", path)
        if kind not in ISSUE_KINDS:
            raise TaskSpecError(_err(path, f"kind must be a PLATE issue type: {sorted(ISSUE_KINDS)}"))
        level = _require_str(data.get("level"), "level", path)
        if level not in LEVELS:
            raise TaskSpecError(_err(path, f"level must be one of {sorted(LEVELS)}"))
        route = _require_str(data.get("route"), "route", path)
        if route not in ROUTES:
            raise TaskSpecError(_err(path, f"route must be one of {sorted(ROUTES)}"))
        _validate_typed_fields(data.get("inputs"), "inputs", path)
        _validate_typed_fields(data.get("outputs"), "outputs", path)
        acceptance = data.get("acceptance")
        if not isinstance(acceptance, dict):
            raise TaskSpecError(_err(path, "acceptance must be a mapping"))
        checks = acceptance.get("checks")
        if not isinstance(checks, list) or not checks:
            raise TaskSpecError(_err(path, "acceptance.checks must be a non-empty list"))
        for index, check in enumerate(checks):
            if not isinstance(check, str) or not check.strip():
                raise TaskSpecError(_err(path, f"acceptance.checks[{index}] must be a non-empty string"))
        success_signal = acceptance.get("success_signal")
        if not isinstance(success_signal, str) or not success_signal.strip():
            raise TaskSpecError(_err(path, "acceptance.success_signal must be a non-empty string"))
        _validate_tools(data.get("tools"), path)
        approval = _require_str(data.get("approval"), "approval", path)
        if approval not in APPROVAL_GATES:
            raise TaskSpecError(_err(path, f"approval must be one of {sorted(APPROVAL_GATES)}"))
        _validate_model_policy(data.get("model_policy"), path, approval)
        budget = data.get("budget")
        if not isinstance(budget, dict):
            raise TaskSpecError(_err(path, "budget must be a mapping"))
        max_tokens = budget.get("max_tokens_per_run")
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise TaskSpecError(_err(path, "budget.max_tokens_per_run must be a positive integer"))
        if set(budget) - {"max_tokens_per_run"}:
            raise TaskSpecError(_err(path, "budget has unknown keys"))
        allowed_top = {
            "task_spec_version",
            "id",
            "role",
            "kind",
            "level",
            "route",
            "inputs",
            "outputs",
            "acceptance",
            "tools",
            "model_policy",
            "approval",
            "budget",
            "next",
        }
        extra_top = set(data) - allowed_top
        if extra_top:
            raise TaskSpecError(_err(path, f"unknown top-level keys: {sorted(extra_top)}"))
        skip_self = None
        if known_task_ids is not None:
            skip_self = frozenset(i for i in known_task_ids if i != task_id)
        _validate_next(data.get("next"), path, known_ids=skip_self)
    except TaskSpecError as exc:
        errors.append(str(exc))
    return TaskSpecValidationReport(
        path=path,
        task_id=task_id,
        valid=not errors,
        errors=tuple(errors),
    )


def infer_role_from_issue(kind: str, labels: Iterable[str]) -> str | None:
    """Best-effort role hint from issue type and labels (routing aid; not a validator).

    Crew roles are **not** GitHub labels (#1327). Infer from issue type plus stable
    ``area:*`` (and related) labels only.
    """
    label_set = {label.strip().lower() for label in labels if label.strip()}

    if kind == "Question":
        return "customer-success-manager"
    if kind == "Research":
        if "area:marketing" in label_set:
            return "market-researcher"
        return "research-agent"
    if kind == "Design":
        if "area:marketing" in label_set:
            return "advertising-designer"
        if "area:frontend" in label_set:
            return "interaction-designer"
        return "design-researcher"
    if kind == "Bug":
        if "area:tests" in label_set:
            return "ci-engineer"
        if "area:infra" in label_set:
            return "live-ops-engineer"
        if "area:security" in label_set:
            return "security-auditor"
        return "software-engineer"
    if kind == "Documentation":
        if "area:marketing" in label_set:
            return "marketing-specialist"
        return "wiki-editor"
    if kind == "Release":
        return "project-manager"
    if kind == "Epic":
        if "area:agent" in label_set:
            return "team-lead"
        return "project-manager"
    if kind in ("Feature", "Feedback Response"):
        if "area:marketing" in label_set:
            return "marketing-specialist"
        if "area:product" in label_set:
            return "product-manager"
        if "area:frontend" in label_set:
            return "user-experience-engineer"
        if "area:infra" in label_set:
            return "devops-engineer"
        if "area:agent" in label_set:
            return "team-lead"
        if "area:backend" in label_set:
            return "software-engineer"
        if "area:security" in label_set:
            return "security-auditor"
    if kind == "Audit":
        if "area:marketing" in label_set:
            return "marketing-specialist"
        return "research-agent"
    return None


def resolve_effective_tool_allow_list(tools: dict[str, Any]) -> frozenset[str]:
    allow = set(tools.get("allow") or [])
    profiles = tools.get("profiles") or []
    if profiles:
        allow.update(tools_for_named_profiles(profiles))
    return frozenset(allow)


def validate_task_spec_paths(
    paths: Iterable[Path],
    *,
    cross_reference: bool = True,
) -> list[TaskSpecValidationReport]:
    path_list = [Path(p).resolve() for p in paths]
    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in path_list:
        documents.append((path, load_task_spec_yaml(path)))
    known_ids = frozenset(
        doc.get("id") for _, doc in documents if isinstance(doc.get("id"), str)
    )
    reports: list[TaskSpecValidationReport] = []
    for path, doc in documents:
        reports.append(
            validate_task_spec_document(
                doc,
                path=str(path),
                known_task_ids=known_ids if cross_reference else None,
            )
        )
    return reports


def validate_tasks_directory(
    repo_root: Path,
    *,
    tasks_dir: Path | None = None,
) -> tuple[bool, list[TaskSpecValidationReport]]:
    root = repo_root.resolve()
    directory = (tasks_dir or root / ".agentic" / "tasks").resolve()
    if not directory.is_dir():
        return True, []
    yaml_paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not yaml_paths:
        return True, []
    reports = validate_task_spec_paths(yaml_paths)
    return all(r.valid for r in reports), reports


def cmd_validate_task_specs(args: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m plate_core.task_spec",
        description="Validate PLATE agent crew task specs under .agentic/tasks/",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--tasks-dir",
        default="",
        help="Override tasks directory (default: <repo-root>/.agentic/tasks)",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help="Validate a single YAML file (repeatable); skips directory scan",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parsed = parser.parse_args(args)
    repo_root = Path(parsed.repo_root).resolve()
    if parsed.paths:
        reports = validate_task_spec_paths([Path(p) for p in parsed.paths])
        ok = all(r.valid for r in reports)
    else:
        tasks_dir = Path(parsed.tasks_dir).resolve() if parsed.tasks_dir else None
        ok, reports = validate_tasks_directory(repo_root, tasks_dir=tasks_dir)
    if parsed.json:
        print(json.dumps({"valid": ok, "reports": [r.to_dict() for r in reports]}, indent=2))
    else:
        if not reports:
            print(f"No task specs found under {repo_root / '.agentic' / 'tasks'}")
        for report in reports:
            status = "ok" if report.valid else "INVALID"
            print(f"{status}: {report.path}")
            for err in report.errors:
                print(f"  - {err}")
        if not ok:
            print("Task spec validation failed.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    return cmd_validate_task_specs(argv)


if __name__ == "__main__":
    raise SystemExit(main())
