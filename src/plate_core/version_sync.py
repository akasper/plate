"""Helpers for keeping repository version surfaces in sync."""

from __future__ import annotations

import json
import re
from pathlib import Path


_INIT_VERSION_RE = re.compile(r'(?m)^__version__ = "[^"]+"$')
_PYPROJECT_VERSION_RE = re.compile(r'(?m)^version = "[^"]+"$')
_JSON_VERSION_KEY = "version"


def repository_version_targets(repo_root: Path) -> list[Path]:
    """Return the canonical repository version files in a stable order."""
    root = repo_root.resolve()
    return [
        root / "src" / "plate_core" / "__init__.py",
        root / "pyproject.toml",
        root / "plugin" / "plugin.json",
        root / ".plugin" / "plugin.json",
        root / ".github" / "plugin" / "marketplace.json",
        root / ".grok-plugin" / "marketplace.json",
    ]


def find_repo_root(start: Path) -> Path:
    """Find the repository root by walking upward from *start*."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "src" / "plate_core" / "__init__.py").exists():
            return candidate
    raise RuntimeError(f"Could not locate repository root from {start}")


def _replace_pattern(path: Path, pattern: re.Pattern[str], replacement: str, *, dry_run: bool) -> None:
    if not path.exists():
        raise RuntimeError(f"Version sync target missing: {path}")
    original = path.read_text(encoding="utf-8")
    updated, count = pattern.subn(replacement, original, 1)
    if count != 1:
        raise RuntimeError(f"Expected exactly one version field in {path}")
    if not dry_run and updated != original:
        path.write_text(updated, encoding="utf-8")


def _update_json(path: Path, version: str, *, dry_run: bool) -> None:
    if not path.exists():
        raise RuntimeError(f"Version sync target missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data[_JSON_VERSION_KEY] = version
    if not dry_run:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _extract_pattern_value(path: Path, pattern: re.Pattern[str], field_name: str) -> str:
    if not path.exists():
        raise RuntimeError(f"Version sync target missing: {path}")
    matches = list(pattern.finditer(path.read_text(encoding="utf-8")))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one version field in {path}")
    line = matches[0].group(0)
    value_match = re.search(r'"([^"]+)"', line)
    if value_match is None:
        raise RuntimeError(f"Could not parse {field_name} version in {path}")
    return value_match.group(1)


def _read_json_version(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Version sync target missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get(_JSON_VERSION_KEY)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Missing string '{_JSON_VERSION_KEY}' field in {path}")
    return value


def read_repository_versions(repo_root: Path) -> dict[str, str]:
    """Read the current version from each canonical repository version file."""
    root = repo_root.resolve()
    targets = repository_version_targets(root)
    # Copilot marketplace (targets[4]) uses metadata + plugins[0]
    copilot_market = json.loads(targets[4].read_text(encoding="utf-8"))
    copilot_meta = copilot_market.get("metadata") or {}
    copilot_plugins = copilot_market.get("plugins") or []
    if not isinstance(copilot_meta.get("version"), str) or not copilot_meta["version"]:
        raise RuntimeError(f"Missing string 'metadata.version' field in {targets[4]}")
    if len(copilot_plugins) != 1 or not isinstance(copilot_plugins[0], dict):
        raise RuntimeError(f"Expected exactly one plugin entry in {targets[4]}")
    copilot_plugin_version = copilot_plugins[0].get("version")
    if not isinstance(copilot_plugin_version, str) or not copilot_plugin_version:
        raise RuntimeError(f"Missing string 'plugins[0].version' field in {targets[4]}")
    if copilot_plugin_version != copilot_meta["version"]:
        raise RuntimeError(
            f"Marketplace manifest version mismatch in {targets[4]}: "
            f"metadata.version={copilot_meta['version']!r}, plugins[0].version={copilot_plugin_version!r}"
        )
    # Grok marketplace (targets[5]) uses plugins[0].version directly (no metadata wrapper)
    grok_market = json.loads(targets[5].read_text(encoding="utf-8"))
    grok_plugins = grok_market.get("plugins") or []
    if len(grok_plugins) != 1 or not isinstance(grok_plugins[0], dict):
        raise RuntimeError(f"Expected exactly one plugin entry in {targets[5]}")
    grok_plugin_version = grok_plugins[0].get("version")
    if not isinstance(grok_plugin_version, str) or not grok_plugin_version:
        raise RuntimeError(f"Missing string 'plugins[0].version' field in {targets[5]}")
    if grok_plugin_version != copilot_meta["version"]:
        raise RuntimeError(
            f"Grok/Copilot marketplace version drift in {targets[5]} vs {targets[4]}: "
            f"grok={grok_plugin_version!r}, copilot={copilot_meta['version']!r}"
        )
    return {
        targets[0].relative_to(root).as_posix(): _extract_pattern_value(targets[0], _INIT_VERSION_RE, "__version__"),
        targets[1].relative_to(root).as_posix(): _extract_pattern_value(targets[1], _PYPROJECT_VERSION_RE, "project"),
        targets[2].relative_to(root).as_posix(): _read_json_version(targets[2]),
        targets[3].relative_to(root).as_posix(): _read_json_version(targets[3]),
        targets[4].relative_to(root).as_posix(): copilot_meta["version"],
        targets[5].relative_to(root).as_posix(): grok_plugin_version,
    }


def sync_repository_version(version: str, repo_root: Path, *, dry_run: bool = False) -> list[Path]:
    """Sync repository version files to *version* and return updated paths."""
    root = repo_root.resolve()
    targets = repository_version_targets(root)
    _replace_pattern(targets[0], _INIT_VERSION_RE, f'__version__ = "{version}"', dry_run=dry_run)
    _replace_pattern(targets[1], _PYPROJECT_VERSION_RE, f'version = "{version}"', dry_run=dry_run)
    for path in targets[2:]:
        if path.name == "marketplace.json":
            data = json.loads(path.read_text(encoding="utf-8"))
            plugins = data.get("plugins")
            if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
                raise RuntimeError(f"Expected exactly one plugin entry in {path}")
            # Copilot style has metadata wrapper; Grok style (and future) only updates the plugin entry
            if isinstance(data.get("metadata"), dict):
                data["metadata"]["version"] = version
            data["plugins"][0]["version"] = version
            if not dry_run:
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            continue
        _update_json(path, version, dry_run=dry_run)
    return targets
