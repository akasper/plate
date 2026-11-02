"""Named MCP tool profiles for plate-mcp (issue #1331).

Hosts discover a filtered subset via ``tools/list``; optional profiles add tools.
Task specs and crew routing can reference profile names in ``tool_allow_profiles``.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

ENV_TOOL_PROFILES = "PLATE_MCP_TOOL_PROFILES"
PROFILE_ALL = "all"
PROFILE_DEFAULT = "default"

# ``default`` expands to these named profiles (task / issue / review / delegation basics).
DEFAULT_PROFILE_EXPAND: tuple[str, ...] = (
    "issue",
    "task",
    "review",
    "delegation",
    "process",
)

KNOWN_PROFILES: frozenset[str] = frozenset(
    {
        PROFILE_ALL,
        PROFILE_DEFAULT,
        *DEFAULT_PROFILE_EXPAND,
        "planning",
        "qanda",
        "release",
        "adoption",
        "config",
        "e2e",
        "artifacts",
        "pm",
        "fleet",
        "monitor",
        "stubs",
        "bug_loop",
        "feature_loop",
        "design",
        "release_media",
        "hybrid",
        "packaging",
        "feature_media",
        "scheduled_ops",
        "collab",
        "ledger",
        "autonomy",
        "migrate",
        "audit",
        "discussions",
        "costs",
    }
)


def profiles_for_tool(name: str) -> frozenset[str]:
    """Return named profiles that include ``name`` (used for filtering and docs)."""
    profiles: set[str] = set()
    if name in ("plate_health", "plate_epic_status", "plate_features"):
        profiles.add("issue")
    elif name.startswith("plate_task_"):
        profiles.add("task")
    elif name in (
        "plate_pr_babysit",
        "plate_get_pr_merge_gates",
        "plate_resolve_review_thread",
        "plate_get_unresolved_review_threads",
        "plate_get_actionable_review_threads",
    ):
        profiles.add("review")
    elif name in (
        "plate_agents",
        "plate_agent",
        "plate_skills",
        "plate_skill",
        "plate_contexts",
        "plate_context",
        "plate_delegate_to_agent",
    ):
        profiles.add("delegation")
    elif name in ("plate_what_next", "plate_feed"):
        profiles.add("process")
    elif name in (
        "plate_plan_epic",
    ) or name.startswith("plate_planning_") or name.startswith("plate_er_planning_"):
        profiles.add("planning")
    elif name in (
        "plate_list_questions",
        "plate_get_question",
        "plate_record_answer",
        "plate_get_answers",
        "plate_synthesize_priorities",
        "plate_create_blocking_question",
        "plate_contemplate",
    ):
        profiles.add("qanda")
    elif name.startswith("plate_release_"):
        profiles.add("release")
    elif (
        name.startswith("plate_bootstrap")
        or name.startswith("plate_adoption_")
        or name.startswith("plate_self_migrate_")
        or name.startswith("plate_import_payload")
        or name.startswith("plate_payload_")
    ):
        profiles.add("adoption")
    elif name.startswith("plate_config_") or name.startswith("plate_hooks_"):
        profiles.add("config")
    elif name in ("init_playwright", "record_e2e_gif", "validate_e2e_tests"):
        profiles.add("e2e")
    elif name.startswith("plate_artifact_"):
        profiles.add("artifacts")
    elif name.startswith("plate_pm_"):
        profiles.add("pm")
    elif name.startswith("plate_fleet_"):
        profiles.add("fleet")
    elif name.startswith("plate_monitor_"):
        profiles.add("monitor")
    elif name.startswith("plate_stub_"):
        profiles.add("stubs")
    elif name.startswith("plate_bug_loop_"):
        profiles.add("bug_loop")
    elif name.startswith("plate_feature_loop_"):
        profiles.add("feature_loop")
    elif name.startswith("plate_design_contract_"):
        profiles.add("design")
    elif name.startswith("plate_release_media_"):
        profiles.add("release_media")
    elif name.startswith("plate_hybrid_"):
        profiles.add("hybrid")
    elif name.startswith("plate_packaging_"):
        profiles.add("packaging")
    elif name.startswith("plate_feature_media_"):
        profiles.add("feature_media")
    elif name.startswith("plate_scheduled_op"):
        profiles.add("scheduled_ops")
    elif name.startswith("plate_collab_"):
        profiles.add("collab")
    elif name.startswith("plate_ledger_"):
        profiles.add("ledger")
    elif name.startswith("plate_autonomy_") or name.startswith("plate_checkpoint_"):
        profiles.add("autonomy")
    elif name.startswith("plate_migrate_"):
        profiles.add("migrate")
    elif name in ("plate_spec_audit", "plate_spec_audit_followups", "plate_perform_information_audit"):
        profiles.add("audit")
    elif "discussion" in name or name == "plate_list_open_ideas":
        profiles.add("discussions")
    elif name == "plate_costs":
        profiles.add("costs")
    else:
        raise KeyError(f"No MCP tool profile mapping for {name!r}")
    return frozenset(profiles)


def expand_profile_names(selected: Iterable[str]) -> set[str]:
    """Expand ``default`` and validate names; ``all`` alone selects every tool."""
    expanded: set[str] = set()
    for raw in selected:
        name = raw.strip().lower()
        if not name:
            continue
        if name == PROFILE_ALL:
            return {PROFILE_ALL}
        if name == PROFILE_DEFAULT:
            expanded.update(DEFAULT_PROFILE_EXPAND)
            continue
        if name not in KNOWN_PROFILES:
            raise ValueError(
                f"Unknown MCP tool profile {name!r}. "
                f"Known: {', '.join(sorted(KNOWN_PROFILES))}"
            )
        expanded.add(name)
    return expanded


def parse_tool_profile_spec(spec: str | None) -> set[str]:
    if spec is None or not str(spec).strip():
        spec = os.environ.get(ENV_TOOL_PROFILES, PROFILE_DEFAULT)
    parts = [p.strip() for p in str(spec).split(",") if p.strip()]
    if not parts:
        parts = [PROFILE_DEFAULT]
    return expand_profile_names(parts)


def parse_tool_profile_spec_from_argv(argv: list[str]) -> str | None:
    """Return explicit profile spec from ``--tool-profiles`` if present."""
    for i, arg in enumerate(argv):
        if arg in ("--tool-profiles", "--mcp-tool-profiles"):
            if i + 1 < len(argv):
                return argv[i + 1]
            raise SystemExit(f"{arg} requires a comma-separated profile list")
        if arg.startswith("--tool-profiles="):
            return arg.split("=", 1)[1]
        if arg.startswith("--mcp-tool-profiles="):
            return arg.split("=", 1)[1]
    return None


def tool_visible(name: str, active_profiles: set[str]) -> bool:
    if PROFILE_ALL in active_profiles:
        return True
    tool_profiles = profiles_for_tool(name)
    return bool(tool_profiles & active_profiles)


def filter_tool_definitions(tools: list[dict], active_profiles: set[str]) -> list[dict]:
    return [t for t in tools if tool_visible(t.get("name", ""), active_profiles)]


def describe_active_profiles(active_profiles: set[str]) -> str:
    if PROFILE_ALL in active_profiles:
        return PROFILE_ALL
    return ",".join(sorted(active_profiles))


# Module state set when plate-mcp ``run()`` starts (stdio session).
_session_profiles: set[str] | None = None
_session_profiles_enforced: bool = False


def configure_mcp_tool_profiles(spec: str | None = None) -> set[str]:
    """Resolve and store profiles for this MCP server process."""
    global _session_profiles, _session_profiles_enforced
    argv_spec = parse_tool_profile_spec_from_argv(sys.argv)
    resolved = parse_tool_profile_spec(argv_spec if argv_spec is not None else spec)
    _session_profiles = resolved
    _session_profiles_enforced = True
    return resolved


def get_active_mcp_tool_profiles() -> set[str]:
    if _session_profiles is not None:
        return _session_profiles
    return parse_tool_profile_spec(None)


def mcp_tool_profiles_enforced() -> bool:
    return _session_profiles_enforced


def reset_mcp_tool_profile_session() -> None:
    """Test helper: clear session profile state."""
    global _session_profiles, _session_profiles_enforced
    _session_profiles = None
    _session_profiles_enforced = False


def assert_tool_allowed(name: str) -> None:
    if not mcp_tool_profiles_enforced():
        return
    active = get_active_mcp_tool_profiles()
    if tool_visible(name, active):
        return
    raise ValueError(
        f"MCP tool {name!r} is not enabled for profiles: "
        f"{describe_active_profiles(active)}. "
        f"Set {ENV_TOOL_PROFILES}=all or add a profile that includes this tool."
    )
