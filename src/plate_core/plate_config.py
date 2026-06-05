""".plate root configuration schema, report, parser, validator, and init helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


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
    "release": {
        "triggers": [],
        "default_track": None,
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


@dataclass
class PlateConfigReport:
    repo_root: str
    path: str
    present: bool
    valid: bool
    source: str
    config: Dict[str, Any]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if not payload.get("errors"):
            payload.pop("errors", None)
        return payload


class PlateConfigError(ValueError):
    """Raised for invalid .plate configuration."""


def _is_valid_semver_like(value: str) -> bool:
    parts = value.split(".")
    if not (2 <= len(parts) <= 3):
        return False
    try:
        return all(int(part) >= 0 for part in parts)
    except ValueError:
        return False


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _plate_path(repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root else Path(".")
    return root / ".plate"


def validate_plate_config(config: Dict[str, Any], *, strict: bool = False) -> None:
    """Validate .plate config against schema rules."""

    if "version" not in config:
        raise PlateConfigError("missing required 'version' field")
    version = config["version"]
    if not isinstance(version, str) or not _is_valid_semver_like(version):
        raise PlateConfigError(f"invalid version format: {version!r}")

    allowed = {"version", "methodology", "extensions", "overrides", "release"}
    if strict:
        unknown = sorted(set(config) - allowed)
        if unknown:
            raise PlateConfigError(f"unknown top-level keys: {', '.join(unknown)}")

    for key in ("methodology", "extensions", "overrides", "release"):
        if key in config and not isinstance(config[key], dict):
            raise PlateConfigError(f"'{key}' must be an object if present")


def load_plate_config(repo_root: Path | None = None) -> PlateConfig:
    """Load and resolve .plate config with precedence defaults < local."""

    local_path = _plate_path(repo_root)
    local: Dict[str, Any] = {}
    if local_path.exists():
        try:
            local = json.loads(local_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PlateConfigError(f"invalid JSON in .plate: {exc}") from exc

    merged = _deep_merge(DEFAULT_CONFIG, local)
    validate_plate_config(merged)
    return PlateConfig.from_dict(merged)


def get_plate_config_report(repo_root: Path | None = None) -> PlateConfigReport:
    """Return effective .plate state for CLI/MCP surfaces."""

    local_path = _plate_path(repo_root)
    root = str(local_path.parent.resolve())
    try:
        config = load_plate_config(local_path.parent).to_dict()
        return PlateConfigReport(
            repo_root=root,
            path=str(local_path),
            present=local_path.exists(),
            valid=True,
            source="local_file" if local_path.exists() else "defaults",
            config=config,
        )
    except PlateConfigError as exc:
        return PlateConfigReport(
            repo_root=root,
            path=str(local_path),
            present=local_path.exists(),
            valid=False,
            source="local_file" if local_path.exists() else "defaults",
            config=dict(DEFAULT_CONFIG),
            errors=[str(exc)],
        )


def save_plate_config(
    config: PlateConfig,
    repo_root: Path | None = None,
    *,
    overwrite: bool = True,
) -> Path:
    """Write .plate to disk."""

    path = _plate_path(repo_root)
    if path.exists() and not overwrite:
        raise PlateConfigError(".plate already exists; use --force to overwrite")
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def init_plate_config(repo_root: Path | None = None, *, force: bool = False) -> PlateConfigReport:
    """Create a baseline .plate file if absent (or overwrite with --force)."""

    path = save_plate_config(PlateConfig.from_dict(DEFAULT_CONFIG), repo_root, overwrite=force)
    return get_plate_config_report(path.parent)
