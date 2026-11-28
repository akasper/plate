"""Single MCP tool registry: list metadata, dispatch, and profile consistency (#1475)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .curiosity_tools import CURIOSITY_TOOLS
from .tool_definitions import MCP_TOOL_DEFINITIONS, tool_definition_names


@dataclass(frozen=True)
class McpToolRecord:
    name: str
    definition: dict[str, Any]
    mutating: bool
    profile_names: frozenset[str]


_EXPLICIT_READ_ONLY = frozenset(
    {
        "plate_health",
        "plate_epic_status",
        "plate_features",
        "plate_pr_verify",
        "plate_spec_audit",
        "plate_list_questions",
        "plate_get_question",
        "plate_get_answers",
        "plate_synthesize_priorities",
        "plate_list_discussions",
        "plate_get_discussion",
        "plate_list_discussion_comments",
        "plate_list_discussion_categories",
        "plate_list_open_ideas",
        "plate_perform_test_coverage_audit",
        "validate_e2e_tests",
    }
)

_EXPLICIT_MUTATING = frozenset(
    {
        "plate_backfill_answers",
    }
)


def _is_mutating(name: str) -> bool:
    if name in _EXPLICIT_MUTATING:
        return True
    if name in _EXPLICIT_READ_ONLY:
        return False
    if name.startswith("plate_get_") or name.startswith("plate_list_"):
        return False
    if name in CURIOSITY_TOOLS and name not in (
        "plate_record_answer",
        "plate_create_blocking_question",
        "plate_backfill_answers",
    ):
        return False
    if any(
        name.startswith(p)
        for p in (
            "plate_create_",
            "plate_add_",
            "plate_record_",
            "plate_import_",
            "plate_bootstrap",
            "plate_migrate_",
            "plate_adoption_",
            "plate_release_cut",
            "plate_release_finalize",
            "plate_release_repair",
            "plate_resolve_",
            "plate_delegate_",
            "plate_task_",
            "init_playwright",
            "record_e2e_gif",
        )
    ):
        return True
    return False


def _profiles_for(name: str) -> frozenset[str]:
    from .tool_profiles import profiles_for_tool

    return profiles_for_tool(name)


def build_tool_registry() -> dict[str, McpToolRecord]:
    out: dict[str, McpToolRecord] = {}
    for definition in MCP_TOOL_DEFINITIONS:
        name = str(definition["name"])
        out[name] = McpToolRecord(
            name=name,
            definition=definition,
            mutating=_is_mutating(name),
            profile_names=_profiles_for(name),
        )
    return out


def listed_tool_names() -> frozenset[str]:
    return tool_definition_names()


def dispatched_tool_names() -> frozenset[str]:
    """Tool names with handlers in ``mcp_server.MCP_TOOL_HANDLERS``."""
    from ..mcp_server import MCP_TOOL_HANDLERS

    names = set(MCP_TOOL_HANDLERS.keys())
    names.update(CURIOSITY_TOOLS.keys())
    return frozenset(names)


def dispatchable_tool_names() -> frozenset[str]:
    return dispatched_tool_names()


def assert_catalog_dispatch_parity() -> None:
    listed = listed_tool_names()
    dispatched = dispatched_tool_names()
    if listed != dispatched:
        catalog_only = sorted(listed - dispatched)
        dispatch_only = sorted(dispatched - listed)
        raise AssertionError(
            "MCP catalog/dispatch drift: "
            f"catalog_only={catalog_only!r} dispatch_only={dispatch_only!r}"
        )


def assert_registry_consistency() -> None:
    listed = listed_tool_names()
    registry = build_tool_registry()
    if listed != frozenset(registry.keys()):
        missing = listed - frozenset(registry.keys())
        extra = frozenset(registry.keys()) - listed
        raise AssertionError(
            f"MCP registry drift: missing={sorted(missing)!r} extra={sorted(extra)!r}"
        )
    for name in listed:
        _profiles_for(name)


_execute_tool: Callable[[str, dict[str, Any]], Any] | None = None


def register_tool_executor(fn: Callable[[str, dict[str, Any]], Any]) -> None:
    global _execute_tool
    _execute_tool = fn


def execute_tool(name: str, args: dict[str, Any]) -> Any:
    if _execute_tool is None:
        raise RuntimeError("MCP tool executor not registered")
    return _execute_tool(name, args)


def tool_definitions_for_list() -> list[dict[str, Any]]:
    return list(MCP_TOOL_DEFINITIONS)