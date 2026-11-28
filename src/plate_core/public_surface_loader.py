"""Load live PLATE CLI and MCP public surfaces (#1546).

Import-first loading with ``ast.literal_eval`` fallback only. No ``exec`` and no
stdio MCP session probing — when both paths fail, callers get an explicit error.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

_MCP_SERVER_PATH = Path(__file__).resolve().parent / "mcp_server.py"


def load_cli_tree() -> Any:
    """Return the root ``argparse`` parser from ``plate_core.cli.build_parser()``."""
    from plate_core.cli import build_parser

    return build_parser()


def _mcp_tool_definitions_via_import() -> list[dict[str, Any]] | None:
    for module_name, attr in (
        ("plate_core.mcp.tool_definitions", "MCP_TOOL_DEFINITIONS"),
        ("plate_core.mcp_server", "MCP_TOOL_DEFINITIONS"),
    ):
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            continue
        raw = getattr(mod, attr, None)
        if raw is not None:
            return list(raw)
    for module_name in ("plate_core.mcp.tool_definitions", "plate_core.mcp_server"):
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            continue
        fn = getattr(mod, "tool_definitions_for_list", None)
        if callable(fn):
            return list(fn())
    return None


def _mcp_tool_definitions_via_literal_eval() -> list[dict[str, Any]]:
    source = _MCP_SERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "all_tools":
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    continue
                if isinstance(value, list):
                    return value
    raise RuntimeError("Could not literal_eval all_tools from mcp_server.py")


def load_mcp_tool_definitions() -> list[dict[str, Any]]:
    """Return MCP tool definition dicts (``tools/list`` shape) from live code."""
    tools = _mcp_tool_definitions_via_import()
    if tools is None:
        tools = _mcp_tool_definitions_via_literal_eval()
    return tools