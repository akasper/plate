"""Load live PLATE public surfaces and compare against the stable snapshot (#1058)."""

from __future__ import annotations

import argparse
import ast
import importlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "docs" / "plate" / "research" / "public-surface-inventory.md"
LABELS_PATH = REPO_ROOT / ".github" / "labels.yml"
MCP_SERVER_PATH = REPO_ROOT / "src" / "plate_core" / "mcp_server.py"
SNAPSHOT_VERSION = 1


def parse_inventory_stable_cli_invocations(inventory_text: str) -> set[str]:
    """Return argparse paths like ``agents list`` from section 1.2 stable rows."""
    invocations: set[str] = set()
    in_section = False
    for line in inventory_text.splitlines():
        if line.startswith("### 1.2 Subcommand invocations"):
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break
        if not in_section or not line.startswith("|"):
            continue
        if line.startswith("| Invocation") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        if parts[1].strip().lower() != "stable":
            continue
        raw = parts[0].strip()
        m = re.match(r"`gh plate (.+?)`", raw)
        if m:
            invocations.add(m.group(1).strip())
    return invocations


def parse_inventory_stable_mcp_tools(inventory_text: str) -> set[str]:
    """Return stable MCP tool names from section 2.2 profile tables."""
    tools: set[str] = set()
    in_section = False
    for line in inventory_text.splitlines():
        if line.startswith("### 2.2 Full tool catalog"):
            in_section = True
            continue
        if in_section and line.startswith("### 2.3"):
            break
        if not in_section or not line.startswith("|"):
            continue
        if line.startswith("| Tool") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        if parts[1].strip().lower() != "stable":
            continue
        m = re.match(r"`([^`]+)`", parts[0].strip())
        if m:
            tools.add(m.group(1))
    return tools


def parse_inventory_stable_labels(inventory_text: str) -> set[str]:
    """Return stable label names from section 6."""
    labels: set[str] = set()
    in_section = False
    for line in inventory_text.splitlines():
        if line.startswith("## 6. Labels"):
            in_section = True
            continue
        if in_section and line.startswith("## Gaps"):
            break
        if not in_section or not line.startswith("|"):
            continue
        if line.startswith("| Label") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        if parts[1].strip().lower() != "stable":
            continue
        m = re.match(r"`([^`]+)`", parts[0].strip())
        if m:
            labels.add(m.group(1))
    return labels


def load_inventory_text(path: Path | None = None) -> str:
    return (path or INVENTORY_PATH).read_text(encoding="utf-8")


def _resolve_subparser(root: argparse.ArgumentParser, parts: Iterable[str]) -> argparse.ArgumentParser | None:
    current: argparse.ArgumentParser = root
    for part in parts:
        subparsers_action = None
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                subparsers_action = action
                break
        if subparsers_action is None:
            return None
        choice = subparsers_action.choices.get(part)
        if choice is None:
            return None
        current = choice
    return current


def _option_strings(parser: argparse.ArgumentParser) -> list[str]:
    collected: set[str] = set()
    for action in parser._actions:
        for opt in action.option_strings:
            if opt:
                collected.add(opt)
    return sorted(collected)


def load_live_cli(invocations: set[str]) -> dict[str, list[str]]:
    from plate_core.cli import build_parser

    root = build_parser()
    live: dict[str, list[str]] = {}
    for inv in sorted(invocations):
        parts = inv.split()
        sub = _resolve_subparser(root, parts)
        if sub is None:
            live[inv] = []
        else:
            live[inv] = _option_strings(sub)
    return live


def load_live_labels() -> list[str]:
    data = yaml.safe_load(LABELS_PATH.read_text(encoding="utf-8")) or []
    return sorted(str(row["name"]) for row in data if isinstance(row, dict) and row.get("name"))


def _mcp_tools_via_refactor_layout() -> list[dict[str, Any]] | None:
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


def _mcp_tools_via_ast() -> list[dict[str, Any]]:
    source = MCP_SERVER_PATH.read_text(encoding="utf-8")
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


def _mcp_tools_via_stdio() -> list[dict[str, Any]]:
    from unittest.mock import patch

    from plate_core.mcp.tool_profiles import ENV_TOOL_PROFILES, PROFILE_ALL, reset_mcp_tool_profile_session
    from plate_core.mcp_server import run

    os.environ[ENV_TOOL_PROFILES] = PROFILE_ALL
    reset_mcp_tool_profile_session()
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    written: list[dict] = []

    def _capture(obj: dict) -> None:
        written.append(obj)

    with patch("plate_core.mcp_server.sys.stdin", io.StringIO(line)), patch(
        "plate_core.mcp_server._write", side_effect=_capture
    ):
        run()
    reset_mcp_tool_profile_session()
    os.environ.pop(ENV_TOOL_PROFILES, None)
    return written[0]["result"]["tools"]


def load_live_mcp_tools() -> dict[str, dict[str, Any]]:
    """Tool name -> {properties: [...], required: [...]}."""
    tools = _mcp_tools_via_refactor_layout()
    if tools is None:
        try:
            tools = _mcp_tools_via_ast()
        except RuntimeError:
            tools = _mcp_tools_via_stdio()
    by_name: dict[str, dict[str, Any]] = {}
    for entry in tools:
        name = str(entry.get("name") or "")
        if not name:
            continue
        schema = entry.get("inputSchema") or {}
        props = schema.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        required = schema.get("required") or []
        if not isinstance(required, list):
            required = []
        by_name[name] = {
            "properties": sorted(str(k) for k in props.keys()),
            "required": sorted(str(k) for k in required),
        }
    return by_name


def _schema_slice(tool_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "properties": sorted(tool_schema.get("properties") or []),
        "required": sorted(tool_schema.get("required") or []),
    }


def build_stable_snapshot(
    *,
    inventory_path: Path | None = None,
    inventory_text: str | None = None,
) -> dict[str, Any]:
    text = inventory_text if inventory_text is not None else load_inventory_text(inventory_path)
    cli_invocations = parse_inventory_stable_cli_invocations(text)
    mcp_stable = parse_inventory_stable_mcp_tools(text)
    label_stable = parse_inventory_stable_labels(text)

    live_cli = load_live_cli(cli_invocations)
    live_mcp = load_live_mcp_tools()
    live_labels = load_live_labels()

    mcp_out: dict[str, Any] = {}
    for name in sorted(mcp_stable):
        if name in live_mcp:
            mcp_out[name] = _schema_slice(live_mcp[name])

    labels_out = sorted(n for n in label_stable if n in live_labels)

    return {
        "schema_version": SNAPSHOT_VERSION,
        "inventory_ref": "docs/plate/research/public-surface-inventory.md",
        "cli": live_cli,
        "mcp_tools": mcp_out,
        "labels": labels_out,
    }


def load_deprecations(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected JSON list of deprecation entries")
    return data


def _is_deprecated(deprecations: list[dict[str, Any]], kind: str, name: str) -> bool:
    for row in deprecations:
        if row.get("kind") == kind and row.get("name") == name:
            return True
    return False


def compare_stable_surface(
    snapshot: dict[str, Any],
    *,
    deprecations: list[dict[str, Any]] | None = None,
    live_cli: dict[str, list[str]] | None = None,
    live_mcp: dict[str, dict[str, Any]] | None = None,
    live_labels: list[str] | None = None,
) -> list[str]:
    """Return human-readable contract violations (empty when satisfied)."""
    deprecations = deprecations or []
    errors: list[str] = []

    cli_keys = set(snapshot.get("cli") or {})
    live_cli = live_cli if live_cli is not None else load_live_cli(cli_keys)
    for inv, snap_flags in sorted((snapshot.get("cli") or {}).items()):
        if inv not in live_cli:
            if not _is_deprecated(deprecations, "cli_invocation", inv):
                errors.append(f"stable CLI invocation removed or renamed: {inv!r}")
            continue
        live_flags = set(live_cli.get(inv) or [])
        for flag in snap_flags:
            if flag not in live_flags:
                key = f"{inv}:{flag}"
                if not _is_deprecated(deprecations, "cli_flag", key):
                    errors.append(f"stable CLI flag missing: {key!r}")

    mcp_snap = snapshot.get("mcp_tools") or {}
    live_mcp = live_mcp if live_mcp is not None else load_live_mcp_tools()
    for name, snap_schema in sorted(mcp_snap.items()):
        if name not in live_mcp:
            if not _is_deprecated(deprecations, "mcp_tool", name):
                errors.append(f"stable MCP tool removed or renamed: {name!r}")
            continue
        live_schema = live_mcp[name]
        snap_props = set(snap_schema.get("properties") or [])
        live_props = set(live_schema.get("properties") or [])
        for prop in snap_props:
            if prop not in live_props:
                key = f"{name}:{prop}"
                if not _is_deprecated(deprecations, "mcp_property", key):
                    errors.append(f"stable MCP input property removed: {key!r}")
        snap_required = set(snap_schema.get("required") or [])
        live_required = set(live_schema.get("required") or [])
        for req in live_required - snap_required:
            key = f"{name}:{req}"
            if not _is_deprecated(deprecations, "mcp_required_field", key):
                errors.append(f"new required MCP input field (breaking): {key!r}")

    snap_labels = set(snapshot.get("labels") or [])
    live_labels_set = set(live_labels if live_labels is not None else load_live_labels())
    for label in sorted(snap_labels):
        if label not in live_labels_set:
            if not _is_deprecated(deprecations, "label", label):
                errors.append(f"stable label removed or renamed: {label!r}")

    return errors