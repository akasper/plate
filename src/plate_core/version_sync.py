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
    match = pattern.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"Expected exactly one version field in {path}")
    line = match.group(0)
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
    return {
        targets[0].relative_to(root).as_posix(): _extract_pattern_value(targets[0], _INIT_VERSION_RE, "__version__"),
        targets[1].relative_to(root).as_posix(): _extract_pattern_value(targets[1], _PYPROJECT_VERSION_RE, "project"),
        targets[2].relative_to(root).as_posix(): _read_json_version(targets[2]),
        targets[3].relative_to(root).as_posix(): _read_json_version(targets[3]),
    }


def sync_repository_version(version: str, repo_root: Path, *, dry_run: bool = False) -> list[Path]:
    """Sync repository version files to *version* and return updated paths."""
    root = repo_root.resolve()
    targets = repository_version_targets(root)
    _replace_pattern(targets[0], _INIT_VERSION_RE, f'__version__ = "{version}"', dry_run=dry_run)
    _replace_pattern(targets[1], _PYPROJECT_VERSION_RE, f'version = "{version}"', dry_run=dry_run)
    for path in targets[2:]:
        _update_json(path, version, dry_run=dry_run)
    return targets
