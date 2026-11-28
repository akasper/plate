"""Generate stable CLI and MCP reference markdown from code and #1056 classification."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .cli import build_parser
from .mcp.tool_profiles import list_mcp_tool_names

INVENTORY_REL = Path("docs/plate/research/public-surface-inventory.md")
REFERENCE_REL = Path("docs/cli-mcp-reference.md")
_GENERATED_BEGIN = "<!-- PLATE-GENERATED:BEGIN cli-mcp-reference -->"
_GENERATED_END = "<!-- PLATE-GENERATED:END cli-mcp-reference -->"


@dataclass(frozen=True)
class CliCommandRef:
    invocation: str
    summary: str
    flags: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class McpToolRef:
    name: str
    description: str
    parameters: tuple[tuple[str, str], ...]


def _repo_paths(repo_root: Path) -> tuple[Path, Path]:
    return repo_root / INVENTORY_REL, repo_root / REFERENCE_REL


def load_stable_surface_keys(repo_root: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Parse stable CLI invocations and MCP tool names from the public-surface inventory."""
    inventory_path = repo_root / INVENTORY_REL
    text = inventory_path.read_text(encoding="utf-8")
    cli_stable: set[str] = set()
    mcp_stable: set[str] = set()
    section = None
    for line in text.splitlines():
        if line.startswith("### 1.2 Subcommand invocations"):
            section = "cli"
            continue
        if line.startswith("### 1.3 "):
            section = None
            continue
        if line.startswith("### 2.2 Full tool catalog"):
            section = "mcp"
            continue
        if line.startswith("### 2.3 "):
            section = None
            continue
        if section == "cli" and "| stable |" in line:
            match = re.search(r"`gh plate ([^`]+)`", line)
            if match:
                cli_stable.add(match.group(1).strip())
        if section == "mcp" and "| stable |" in line:
            match = re.search(r"`([^`]+)`", line)
            if match:
                name = match.group(1)
                if re.match(r"^(plate_|init_|record_|validate_)", name):
                    mcp_stable.add(name)
    return frozenset(cli_stable), frozenset(mcp_stable)


def _find_parser(root: argparse.ArgumentParser, parts: tuple[str, ...]) -> argparse.ArgumentParser | None:
    parser = root
    for part in parts:
        sub_actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not sub_actions:
            return None
        choices = sub_actions[0].choices
        if part not in choices:
            return None
        parser = choices[part]
    return parser


def _subcommand_help(parser: argparse.ArgumentParser, parts: tuple[str, ...]) -> str:
    current = parser
    last_help = ""
    for part in parts:
        sub_actions = [a for a in current._actions if isinstance(a, argparse._SubParsersAction)]
        if not sub_actions:
            break
        sub = sub_actions[0]
        for act in sub._choices_actions or []:
            if act.dest == part and act.help:
                last_help = act.help.strip()
        if part not in sub.choices:
            break
        current = sub.choices[part]
    summary = (current.description or last_help or "").strip()
    summary = re.sub(r"\s+", " ", summary)
    return summary


def _walk_cli_leaves(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    sub_actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not sub_actions:
        return [prefix]
    out: list[tuple[str, ...]] = []
    for name in sorted(sub_actions[0].choices):
        out.extend(_walk_cli_leaves(sub_actions[0].choices[name], prefix + (name,)))
    return out


def _collect_cli_flags(leaf: argparse.ArgumentParser) -> list[tuple[str, str]]:
    flags: list[tuple[str, str]] = []
    for action in leaf._actions:
        if not action.option_strings:
            continue
        if action.option_strings == ["-h", "--help"]:
            continue
        opt = action.option_strings[0]
        help_text = re.sub(r"\s+", " ", (action.help or "").strip())
        flags.append((opt, help_text))
    flags.sort(key=lambda item: item[0])
    return flags


def collect_stable_cli_commands(repo_root: Path) -> list[CliCommandRef]:
    stable_cli, _ = load_stable_surface_keys(repo_root)
    root = build_parser()
    by_invocation: dict[str, CliCommandRef] = {}
    for parts in _walk_cli_leaves(root):
        invocation = " ".join(parts)
        if invocation not in stable_cli:
            continue
        leaf = _find_parser(root, parts)
        if leaf is None:
            raise ValueError(f"stable CLI invocation missing parser: gh plate {invocation}")
        by_invocation[invocation] = CliCommandRef(
            invocation=invocation,
            summary=_subcommand_help(root, parts),
            flags=tuple(_collect_cli_flags(leaf)),
        )
    missing = stable_cli - set(by_invocation)
    if missing:
        raise ValueError(f"stable CLI invocations not in parser: {sorted(missing)}")
    return [by_invocation[key] for key in sorted(by_invocation)]


def _extract_description(chunk: str) -> str:
    match = re.search(r'"description":\s*\((.*?)\)\s*,', chunk, re.DOTALL)
    if match:
        parts = re.findall(r'"([^"]*)"', match.group(1))
        return re.sub(r"\s+", " ", "".join(parts)).strip()
    match = re.search(r'"description":\s*"([^"]*)"', chunk)
    if match:
        return match.group(1).strip()
    return ""


def _extract_parameters(chunk: str) -> list[tuple[str, str]]:
    schema_match = re.search(r'"inputSchema":\s*\{', chunk)
    if not schema_match:
        return []
    sub = chunk[schema_match.start() :]
    params: list[tuple[str, str]] = []
    for prop in re.finditer(r'"([a-z][a-z0-9_]*)":\s*\{\s*\n\s+"type":', sub):
        name = prop.group(1)
        block = sub[prop.start() : prop.start() + 800]
        desc = _extract_description(block)
        params.append((name, desc))
    params.sort(key=lambda item: item[0])
    return params


def _mcp_tools_block(repo_root: Path) -> str:
    server_path = repo_root / "src" / "plate_core" / "mcp_server.py"
    text = server_path.read_text(encoding="utf-8")
    start = text.find('elif method == "tools/list":')
    if start < 0:
        raise ValueError("tools/list block not found in mcp_server.py")
    sub = text[start:]
    match = re.search(r"all_tools = \[(.*)\]\s*\n\s*visible_tools", sub, re.DOTALL)
    if not match:
        raise ValueError("all_tools list not found in mcp_server.py")
    return match.group(1)


def _split_mcp_tool_chunks(block: str) -> dict[str, str]:
    names = [m.start() for m in re.finditer(r'"name": "', block)]
    chunks: dict[str, str] = {}
    for i, pos in enumerate(names):
        end = names[i + 1] if i + 1 < len(names) else len(block)
        piece = block[pos:end]
        name_match = re.search(r'"name": "([^"]+)"', piece)
        if name_match:
            chunks[name_match.group(1)] = piece
    return chunks


def collect_stable_mcp_tools(repo_root: Path) -> list[McpToolRef]:
    _, stable_mcp = load_stable_surface_keys(repo_root)
    block = _mcp_tools_block(repo_root)
    parsed_names = set(re.findall(r'"name": "([^"]+)"', block))
    catalog_names = list_mcp_tool_names()
    if parsed_names != set(catalog_names):
        missing = catalog_names - parsed_names
        extra = parsed_names - catalog_names
        raise ValueError(f"MCP tool catalog mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    chunks = _split_mcp_tool_chunks(block)
    refs: list[McpToolRef] = []
    for name in sorted(stable_mcp):
        if name not in chunks:
            raise ValueError(f"stable MCP tool missing from tools/list: {name}")
        refs.append(
            McpToolRef(
                name=name,
                description=_extract_description(chunks[name]),
                parameters=tuple(_extract_parameters(chunks[name])),
            )
        )
    missing = stable_mcp - set(chunks)
    if missing:
        raise ValueError(f"stable MCP tools not in catalog: {sorted(missing)}")
    return refs


def render_cli_mcp_reference_md(repo_root: Path) -> str:
    cli_cmds = collect_stable_cli_commands(repo_root)
    mcp_tools = collect_stable_mcp_tools(repo_root)
    lines = [
        "# CLI and MCP reference (stable surface)",
        "",
        _GENERATED_BEGIN,
        f"<!-- plate_core {__version__} -->",
        "",
        "Adopter-facing **stable** `gh plate` commands and `plate-mcp` tools. Classification is taken from",
        f"[`{INVENTORY_REL.as_posix()}`](plate/research/public-surface-inventory.md) (issue #1056). Command flags and tool",
        "parameters are derived from `plate_core.cli.build_parser()` and `plate-mcp` `tools/list` schemas.",
        "",
        "Regenerate: `python3 scripts/generate-cli-mcp-reference.py`",
        "",
        "## Stable CLI commands",
        "",
        f"**{len(cli_cmds)}** leaf invocations.",
        "",
    ]
    for cmd in cli_cmds:
        lines.append(f"### `gh plate {cmd.invocation}`")
        lines.append("")
        if cmd.summary:
            lines.append(cmd.summary)
            lines.append("")
        if cmd.flags:
            lines.append("| Flag | Description |")
            lines.append("| --- | --- |")
            for opt, help_text in cmd.flags:
                safe = help_text.replace("|", "\\|")
                lines.append(f"| `{opt}` | {safe} |")
            lines.append("")
        else:
            lines.append("_No optional flags beyond `--help`._")
            lines.append("")
    lines.extend(
        [
            "## Stable MCP tools",
            "",
            f"**{len(mcp_tools)}** tools from the stable profiles in the inventory.",
            "",
        ]
    )
    for tool in mcp_tools:
        lines.append(f"### `{tool.name}`")
        lines.append("")
        if tool.description:
            lines.append(tool.description)
            lines.append("")
        if tool.parameters:
            lines.append("| Parameter | Description |")
            lines.append("| --- | --- |")
            for name, desc in tool.parameters:
                safe = desc.replace("|", "\\|")
                lines.append(f"| `{name}` | {safe} |")
            lines.append("")
        else:
            lines.append("_No schema properties (empty object)._")
            lines.append("")
    lines.append(_GENERATED_END)
    lines.append("")
    return "\n".join(lines)


def write_cli_mcp_reference(repo_root: Path) -> Path:
    content = render_cli_mcp_reference_md(repo_root)
    target = repo_root / REFERENCE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return target


def cli_mcp_reference_in_sync(repo_root: Path) -> tuple[bool, list[str]]:
    target = repo_root / REFERENCE_REL
    if not target.is_file():
        return False, [f"missing {REFERENCE_REL.as_posix()}"]
    expected = render_cli_mcp_reference_md(repo_root)
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, [
            f"{REFERENCE_REL.as_posix()} is out of date; run python3 scripts/generate-cli-mcp-reference.py"
        ]
    return True, []