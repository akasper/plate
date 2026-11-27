"""Confine MCP tool arguments discovered from tool schemas (#1475)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .path_confinement import PathConfinementError, confined, session_repo_root
from .tool_definitions import MCP_TOOL_DEFINITIONS

_MCP_SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp_server.py"

# Schema path keys -> handler fallback keys confined alongside the canonical name.
_CANONICAL_PATH_ALIASES: dict[str, str] = {
    "spec_path": "spec",
    "target_dir": "target",
    "escape_hatch_dir": "escape_hatch",
    "fragment_path": "fragment",
    "upstream_root": "upstream_dir",
}

_OR_ALIAS_PATTERN = re.compile(
    r"args\.get\(\s*[\"'](\w+)[\"']\s*\)\s+or\s+args\.get\(\s*[\"'](\w+)[\"']\s*\)"
)
_DISPATCH_BRANCH_SPLIT = re.compile(
    r'(?=(?:if|elif) name == "[^"]+":)'
)

NON_PATH_PARAMETERS = frozenset(
    {
        "repo",
        "target_version",
        "escape_hatch_on_conflict",
        "fragment_slug",
        "category_slug",
        "category_id",
    }
)

LIST_PATH_PARAMETERS = frozenset({"paths", "artifact_paths", "images"})

_PATH_NAME_MARKERS = (
    "_path",
    "_dir",
    "_root",
    "_file",
    "_folder",
)

_EXACT_PATH_PARAMETERS = frozenset(
    {
        "path",
        "spec",
        "spec_path",
        "target_dir",
        "releases_dir",
        "repo_path",
        "base_dir",
        "repo_root",
        "local_root",
        "worktree_root",
        "ledger_base_dir",
        "escape_hatch_dir",
        "escape_hatch",
        "template_repo",
        "upstream_root",
        "upstream_dir",
        "content_path",
        "fragment_path",
        "fragment",
        "gif_path",
        "video_path",
    }
)

_COLLAB_TARGET_TOOLS = frozenset(
    {
        "plate_collab_ownership_claim",
        "plate_collab_ownership_release",
    }
)

_REGISTRY: dict[str, frozenset[str]] | None = None


def _param_is_path_like(param: str, tool_name: str) -> bool:
    if param in NON_PATH_PARAMETERS:
        return False
    if param in _EXACT_PATH_PARAMETERS or param in LIST_PATH_PARAMETERS:
        return True
    lowered = param.lower()
    if any(lowered.endswith(marker) for marker in _PATH_NAME_MARKERS):
        return True
    if param == "target" and tool_name in _COLLAB_TARGET_TOOLS:
        return True
    if param == "target" and tool_name not in _COLLAB_TARGET_TOOLS:
        return False
    return False


def _should_confine_param(tool_name: str, param: str, args: dict[str, Any]) -> bool:
    if param == "target" and tool_name in _COLLAB_TARGET_TOOLS:
        kind = str(args.get("kind") or "path").lower()
        return kind == "path"
    return _param_is_path_like(param, tool_name)


def path_parameters_for_tool(tool_name: str) -> frozenset[str]:
    for definition in MCP_TOOL_DEFINITIONS:
        if definition.get("name") != tool_name:
            continue
        props = (definition.get("inputSchema") or {}).get("properties") or {}
        return frozenset(
            k for k in props if _param_is_path_like(k, tool_name)
        )
    return frozenset()


def effective_path_parameters(tool_name: str) -> frozenset[str]:
    params = set(path_parameters_for_tool(tool_name))
    for canonical, alias in _CANONICAL_PATH_ALIASES.items():
        if canonical in params:
            params.add(alias)
    return frozenset(params)


def build_path_parameter_index() -> dict[str, frozenset[str]]:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY
    index: dict[str, frozenset[str]] = {}
    for definition in MCP_TOOL_DEFINITIONS:
        name = str(definition["name"])
        params = effective_path_parameters(name)
        if params:
            index[name] = params
    _REGISTRY = index
    return index


def all_registered_path_parameters() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for tool_name, params in sorted(build_path_parameter_index().items()):
        for param in sorted(params):
            rows.append((tool_name, param))
    return rows


def _dispatch_tool_blocks() -> list[tuple[str, str]]:
    """Return ``(tool_name, branch_source)`` for every ``if``/``elif`` branch in dispatch."""
    text = _MCP_SERVER_PATH.read_text(encoding="utf-8")
    marker = "def _execute_mcp_tool"
    start = text.index(marker)
    end = text.index("\ndef _handle_tools_call", start)
    dispatch = text[start:end]
    blocks: list[tuple[str, str]] = []
    for part in _DISPATCH_BRANCH_SPLIT.split(dispatch):
        head = re.match(r'(?:if|elif) name == "([^"]+)":', part)
        if not head:
            continue
        blocks.append((head.group(1), part))
    return blocks


def discover_handler_or_arg_aliases() -> list[tuple[str, str, str]]:
    """Scan dispatch for ``args.get(a) or args.get(b)`` fallback pairs per tool branch."""
    pairs: list[tuple[str, str, str]] = []
    for tool_name, part in _dispatch_tool_blocks():
        for match in _OR_ALIAS_PATTERN.finditer(part):
            pairs.append((tool_name, match.group(1), match.group(2)))
    return pairs


def uncovered_handler_path_aliases() -> list[tuple[str, str]]:
    """Return path-like handler fallback keys not in effective_path_parameters."""
    gaps: list[tuple[str, str]] = []
    for tool_name, left, right in discover_handler_or_arg_aliases():
        effective = effective_path_parameters(tool_name)
        for param in (left, right):
            if _param_is_path_like(param, tool_name) and param not in effective:
                gaps.append((tool_name, param))
    # De-duplicate
    return sorted(set(gaps))


def _confine_single(value: Any, root: Path, param: str) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(confined(item, root, cwd_relative=True)) for item in value]
    if isinstance(value, str) and not value.strip():
        return str(confined(".", root, cwd_relative=True))
    return str(confined(value, root, cwd_relative=True))


def confine_tool_arguments(
    tool_name: str,
    args: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    """Return a copy of ``args`` with path-like values confined to ``root``."""
    base = (root or session_repo_root()).resolve()
    params = effective_path_parameters(tool_name)
    if not params:
        return dict(args)
    out = dict(args)
    # Alias spec -> spec_path when only spec is provided
    if "spec_path" in params and "spec" in out and "spec_path" not in out:
        out["spec_path"] = out["spec"]
    if "target_dir" in params and "target" in out and "target_dir" not in out:
        out["target_dir"] = out["target"]
    if "escape_hatch_dir" in params and "escape_hatch" in out and "escape_hatch_dir" not in out:
        out["escape_hatch_dir"] = out["escape_hatch"]
    if "fragment_path" in params and "fragment" in out and not out.get("fragment_path"):
        out["fragment_path"] = out["fragment"]
    if "upstream_root" in params and "upstream_dir" in out and not out.get("upstream_root"):
        out["upstream_root"] = out["upstream_dir"]
    for param in params:
        if param not in out:
            continue
        if not _should_confine_param(tool_name, param, out):
            continue
        try:
            out[param] = _confine_single(out[param], base, param)
        except PathConfinementError as exc:
            raise PathConfinementError(
                f"Parameter {param!r} must stay within the repository root"
            ) from exc
    return out


def resolve_mcp_path(
    args: dict[str, Any],
    key: str,
    default: str | None,
    root: Path | None = None,
) -> str:
    """Resolve a path argument confined at MCP boundary, or confine ``default`` when absent."""
    base = (root or session_repo_root()).resolve()
    if key in args and args[key] is not None:
        return str(args[key])
    if default is None:
        raise ValueError(f"{key} is required")
    return str(confined(default, base, cwd_relative=True))