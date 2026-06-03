""" .plate root configuration schema, parser, validator, and precedence resolver.

Per Epic #89 / Issue #108 design and Issue #129 implementation.

Precedence (lowest to highest):
1. Tool defaults (from plate)
2. Enabled extensions (future)
3. Local .plate (highest)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0",
    "methodology": {
        "epic_naming_pattern": "Epic: {name}",
        "marker_prefix": "PLATES-CORE",
        "feature_workflow": "feature/{slug}",
    },
    "extensions": {
        "enabled": True,
        "sources": [],
        "installed": {},
    },
    "overrides": {},
    # Release ceremony refinement (Epic #306): project-specific config for finalization triggers,
    # default track policy, etc. Common triggers (e.g. docs) in core; others via extensions.
    # Reconciles with user request for .plate/ area (here as sub-key for the existing .plate file convention).
    "release": {
        "triggers": [],  # list of {id, description, command_or_action, human_approval_required?}
        "default_track": None,  # "Major" | "Minor" | "Patch"
    },
}


@dataclass
class PlateConfig:
    version: str = "1.0"
    methodology: Dict[str, Any] = field(default_factory=dict)
    extensions: Dict[str, Any] = field(default_factory=dict)
    overrides: Dict[str, Any] = field(default_factory=dict)
    release: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlateConfig":
        return cls(
            version=data.get("version", "1.0"),
            methodology=data.get("methodology", {}),
            extensions=data.get("extensions", {}),
            overrides=data.get("overrides", {}),
            release=data.get("release", {}),
        )


class PlateConfigError(ValueError):
    """Raised for invalid .plate configuration."""


def validate_plate_config(config: Dict[str, Any]) -> None:
    """Validate .plate config against schema rules."""
    if "version" not in config:
        raise PlateConfigError("missing required 'version' field")
    version = config["version"]
    if not isinstance(version, str) or not _is_valid_semver_like(version):
        raise PlateConfigError(f"invalid version format: {version!r}")
    # methodology, extensions, overrides, release are optional objects for forward compat
    for key in ("methodology", "extensions", "overrides", "release"):
        if key in config and not isinstance(config[key], dict):
            raise PlateConfigError(f"'{key}' must be an object if present")


def _is_valid_semver_like(v: str) -> bool:
    parts = v.split(".")
    if not (2 <= len(parts) <= 3):
        return False
    try:
        return all(int(p) >= 0 for p in parts)
    except ValueError:
        return False


def load_plate_config(repo_root: Path | None = None) -> PlateConfig:
    """Load and resolve .plate config with precedence (defaults < local for MVP)."""
    root = repo_root or Path(".")
    local_path = root / ".plate"
    local: Dict[str, Any] = {}
    if local_path.exists():
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise PlateConfigError(f"invalid JSON in .plate: {e}") from e

    # MVP: defaults overridden by local (extensions merge later)
    merged = {**DEFAULT_CONFIG, **local}
    # Deep merge for nested dicts (simple last-wins for now)
    for k in ("methodology", "extensions", "overrides", "release"):
        if k in local and isinstance(local[k], dict):
            merged[k] = {**DEFAULT_CONFIG.get(k, {}), **local[k]}

    validate_plate_config(merged)
    return PlateConfig.from_dict(merged)


def save_plate_config(config: PlateConfig, repo_root: Path | None = None) -> Path:
    """Write .plate (for gh plate configure etc)."""
    root = repo_root or Path(".")
    path = root / ".plate"
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
