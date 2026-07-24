""".plate root configuration schema, report, parser, validator, and upgrade helpers."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


CURRENT_CONFIG_VERSION = "1.2"
ALLOWED_CONFIG_TOP_LEVEL_KEYS = {"version", "methodology", "extensions", "overrides", "release", "autonomy"}
ALLOWED_EXTENSION_CONTRIBUTION_KEYS = {"methodology", "overrides", "release", "autonomy"}


DEFAULT_CONFIG: dict[str, Any] = {
    "version": CURRENT_CONFIG_VERSION,
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
    "autonomy": {
        "enabled": True,
        "risk_tolerance": "medium",
        # #496: who babysit treats as actionable review feedback (all | bot-only | human-only)
        "pr_review_scope": "all",
        "token_budget": {
            "daily": 50000,
            "per_cycle": 8000,
            "action": "throttle",
        },
        "cost_ceiling_usd": 10.0,
        "schedules_enabled": True,
        "loop": {
            "default_sleep_seconds": 300,
            "max_cycles": None,
        },
    },
}


@dataclass
class PlateConfig:
    version: str = CURRENT_CONFIG_VERSION
    methodology: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)
    release: dict[str, Any] = field(default_factory=dict)
    autonomy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlateConfig":
        return cls(
            version=data.get("version", CURRENT_CONFIG_VERSION),
            methodology=data.get("methodology", {}),
            extensions=data.get("extensions", {}),
            overrides=data.get("overrides", {}),
            release=data.get("release", {}),
            autonomy=data.get("autonomy", {}),
        )


@dataclass
class PlateConfigReport:
    repo_root: str
    path: str
    present: bool
    valid: bool
    source: str
    config: dict[str, Any]
    file_version: str | None = None
    resolved_version: str = CURRENT_CONFIG_VERSION
    upgrade_available: bool = False
    enabled_extensions: list[str] = field(default_factory=list)
    extension_providers: dict[str, str] = field(default_factory=dict)
    extension_path_providers: dict[str, str] = field(default_factory=dict)
    migration_guidance: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("errors", "enabled_extensions", "extension_providers", "extension_path_providers", "migration_guidance"):
            if not payload.get(key):
                payload.pop(key, None)
        return payload


@dataclass
class PlateConfigUpgradeReport:
    repo_root: str
    path: str
    present: bool
    changed: bool
    applied: bool
    previous_version: str | None
    current_version: str
    config: dict[str, Any]
    migration_guidance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload.get("migration_guidance"):
            payload.pop("migration_guidance", None)
        return payload


@dataclass(frozen=True)
class BuiltinExtensionManifest:
    id: str
    provided_by: str
    config: dict[str, Any]


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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _plate_path(repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root else Path(".")
    return root / ".plate"


def _extension_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "plate_extensions.yml"


def _validate_extension_contribution(config: dict[str, Any], *, label: str) -> None:
    unknown = sorted(set(config) - ALLOWED_EXTENSION_CONTRIBUTION_KEYS)
    if unknown:
        raise PlateConfigError(
            f"{label} uses unsupported config keys: {', '.join(unknown)} "
            f"(allowed: {', '.join(sorted(ALLOWED_EXTENSION_CONTRIBUTION_KEYS))})"
        )
    for key, value in config.items():
        if not isinstance(value, dict):
            raise PlateConfigError(f"{label} config section '{key}' must be an object")


@lru_cache(maxsize=1)
def load_builtin_extension_manifests() -> dict[str, BuiltinExtensionManifest]:
    path = _extension_manifest_path()
    if not path.exists():
        raise PlateConfigError(f"builtin extension manifest catalog missing at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PlateConfigError("builtin extension manifest catalog must be a mapping")
    if data.get("schema_version") != 1:
        raise PlateConfigError("builtin extension manifest catalog schema_version must be 1")
    raw_extensions = data.get("extensions")
    if not isinstance(raw_extensions, list):
        raise PlateConfigError("builtin extension manifest catalog 'extensions' must be a list")

    manifests: dict[str, BuiltinExtensionManifest] = {}
    for raw in raw_extensions:
        if not isinstance(raw, dict):
            raise PlateConfigError("builtin extension manifest entries must be mappings")
        ext_id = raw.get("id")
        provided_by = raw.get("provided_by")
        config = raw.get("config", {})
        if not isinstance(ext_id, str) or not ext_id:
            raise PlateConfigError("builtin extension manifest id must be a non-empty string")
        if ext_id in manifests:
            raise PlateConfigError(f"duplicate builtin extension manifest id: {ext_id}")
        if not isinstance(provided_by, str) or not provided_by:
            raise PlateConfigError(f"builtin extension manifest {ext_id} must define provided_by")
        if not isinstance(config, dict):
            raise PlateConfigError(f"builtin extension manifest {ext_id} config must be an object")
        _validate_extension_contribution(config, label=f"builtin extension '{ext_id}'")
        manifests[ext_id] = BuiltinExtensionManifest(
            id=ext_id,
            provided_by=provided_by,
            config=copy.deepcopy(config),
        )
    return manifests


def _normalize_extension_settings(extension_id: str, raw: Any) -> dict[str, Any]:
    if isinstance(raw, bool):
        return {"enabled": raw}
    if not isinstance(raw, dict):
        raise PlateConfigError(
            f"extensions.installed.{extension_id} must be a boolean or object"
        )
    settings = copy.deepcopy(raw)
    enabled = settings.get("enabled", True)
    if not isinstance(enabled, bool):
        raise PlateConfigError(f"extensions.installed.{extension_id}.enabled must be a boolean")
    settings["enabled"] = enabled
    ext_config = settings.get("config", {})
    if ext_config is None:
        ext_config = {}
    if not isinstance(ext_config, dict):
        raise PlateConfigError(f"extensions.installed.{extension_id}.config must be an object")
    _validate_extension_contribution(ext_config, label=f"extension '{extension_id}'")
    settings["config"] = ext_config
    provided_by = settings.get("provided_by")
    if provided_by is not None and not isinstance(provided_by, str):
        raise PlateConfigError(f"extensions.installed.{extension_id}.provided_by must be a string")
    return settings


def _normalize_installed_extensions(config: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(config)
    extensions = normalized.setdefault("extensions", {})
    installed = extensions.get("installed", {})
    if installed is None:
        installed = {}
    if not isinstance(installed, dict):
        raise PlateConfigError("'extensions.installed' must be an object if present")
    normalized_installed: dict[str, Any] = {}
    for extension_id, raw in installed.items():
        if not isinstance(extension_id, str) or not extension_id:
            raise PlateConfigError("extension ids must be non-empty strings")
        normalized_installed[extension_id] = _normalize_extension_settings(extension_id, raw)
    extensions["installed"] = normalized_installed
    return normalized


def validate_plate_config(config: dict[str, Any], *, strict: bool = False) -> None:
    """Validate .plate config against schema rules."""

    if "version" not in config:
        raise PlateConfigError("missing required 'version' field")
    version = config["version"]
    if not isinstance(version, str) or not _is_valid_semver_like(version):
        raise PlateConfigError(f"invalid version format: {version!r}")

    if strict:
        unknown = sorted(set(config) - ALLOWED_CONFIG_TOP_LEVEL_KEYS)
        if unknown:
            raise PlateConfigError(f"unknown top-level keys: {', '.join(unknown)}")

    for key in ("methodology", "extensions", "overrides", "release", "autonomy"):
        if key in config and not isinstance(config[key], dict):
            raise PlateConfigError(f"'{key}' must be an object if present")

    # Autonomy-specific validation (v1.2 schema; rejects invalid risk, non-numeric budget, unknown keys per test and reviews)
    auto = config.get("autonomy", {})
    if isinstance(auto, dict):
        rt = auto.get("risk_tolerance")
        if rt is not None and rt not in ("off", "low", "medium", "high"):
            raise PlateConfigError(f"invalid autonomy.risk_tolerance: {rt!r} (allowed: off/low/medium/high)")
        prs = auto.get("pr_review_scope")
        if prs is not None and prs not in ("all", "bot-only", "human-only"):
            raise PlateConfigError(
                f"invalid autonomy.pr_review_scope: {prs!r} (allowed: all/bot-only/human-only)"
            )
        tb = auto.get("token_budget", {})
        if isinstance(tb, dict):
            for k in ("daily", "per_cycle"):
                v = tb.get(k)
                if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                    raise PlateConfigError(f"autonomy.token_budget.{k} must be integer number, got {v!r}")
            allowed_tb = {"daily", "per_cycle", "action"}
            unk_tb = set(tb) - allowed_tb
            if unk_tb:
                raise PlateConfigError(f"unknown autonomy.token_budget keys: {', '.join(sorted(unk_tb))}")
        allowed_auto = {
            "enabled",
            "risk_tolerance",
            "pr_review_scope",
            "token_budget",
            "cost_ceiling_usd",
            "schedules_enabled",
            "loop",
        }
        unk_auto = set(auto) - allowed_auto
        if unk_auto:
            raise PlateConfigError(f"unknown autonomy keys: {', '.join(sorted(unk_auto))}")
    elif "autonomy" in config:
        raise PlateConfigError("'autonomy' must be an object if present")

    extensions = config.get("extensions", {})
    if isinstance(extensions, dict):
        enabled = extensions.get("enabled", True)
        if not isinstance(enabled, bool):
            raise PlateConfigError("'extensions.enabled' must be a boolean")
        sources = extensions.get("sources", [])
        if not isinstance(sources, list):
            raise PlateConfigError("'extensions.sources' must be a list if present")
        _normalize_installed_extensions(config)


def _migrate_1_0_to_1_1(config: dict[str, Any]) -> dict[str, Any]:
    upgraded = copy.deepcopy(config)
    upgraded = _normalize_installed_extensions(upgraded)
    release = upgraded.get("release", {})
    if release is None:
        release = {}
    if not isinstance(release, dict):
        raise PlateConfigError("'release' must be an object if present")
    upgraded["release"] = _deep_merge(DEFAULT_CONFIG["release"], release)
    upgraded["version"] = "1.1"
    return upgraded


def _migrate_1_1_to_1_2(config: dict[str, Any]) -> dict[str, Any]:
    """Add autonomy section (code DEFAULT is enabled/medium per the autonomous engine vision in #470; migration injects the current DEFAULT_CONFIG values for forward compatibility)."""
    upgraded = copy.deepcopy(config)
    if "autonomy" not in upgraded or not upgraded.get("autonomy"):
        upgraded["autonomy"] = copy.deepcopy(DEFAULT_CONFIG.get("autonomy", {}))
    upgraded["version"] = "1.2"
    return upgraded


MIGRATION_STEPS: dict[str, tuple[str, Any, list[str]]] = {
    "1.0": (
        "1.1",
        _migrate_1_0_to_1_1,
        [
            "Upgrade `.plate` to schema v1.1 so root config files always carry the `release` section and normalized extension settings.",
            "Review any enabled extensions after upgrade with `gh plate config show --json`; built-in extension manifests now contribute config before local overrides.",
        ],
    ),
    "1.1": (
        "1.2",
        _migrate_1_1_to_1_2,
        [
            "Add the 'autonomy' section (code DEFAULT is enabled at 'medium' risk tolerance per Epic #470 autonomous vision; the migration copies the live DEFAULT_CONFIG so new behavior is forward-compatible).",
            "To keep conservative behavior, explicitly set 'enabled: false' and/or 'risk_tolerance: off' (or 'low') in your .plate file. The section is now added with the current code defaults on upgrade.",
        ],
    ),
}


def upgrade_plate_config_dict(
    config: dict[str, Any],
    *,
    target_version: str = CURRENT_CONFIG_VERSION,
) -> tuple[dict[str, Any], list[str], str]:
    """Upgrade a parsed .plate config dict to the current schema version."""

    upgraded = copy.deepcopy(config)
    validate_plate_config(upgraded, strict=False)
    current_version = upgraded["version"]
    guidance: list[str] = []

    while current_version != target_version:
        if current_version not in MIGRATION_STEPS:
            raise PlateConfigError(
                f"no migration path from version {current_version!r} to {target_version!r}"
            )
        _next_version, transform, step_guidance = MIGRATION_STEPS[current_version]
        upgraded = transform(upgraded)
        guidance.extend(step_guidance)
        current_version = upgraded["version"]

    validate_plate_config(upgraded, strict=False)
    return upgraded, guidance, config["version"]


def _flatten_config_paths(data: dict[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for key, value in data.items():
        next_prefix = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            paths.extend(_flatten_config_paths(value, next_prefix))
        else:
            paths.append(next_prefix)
    return paths


def _resolve_extension_layer(
    local_config: dict[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, str], dict[str, str]]:
    extensions = local_config.get("extensions", {})
    if not extensions.get("enabled", True):
        return {}, [], {}, {}

    manifests = load_builtin_extension_manifests()
    installed = _normalize_installed_extensions(local_config).get("extensions", {}).get("installed", {})

    layer: dict[str, Any] = {}
    enabled_extensions: list[str] = []
    extension_providers: dict[str, str] = {}
    extension_path_providers: dict[str, str] = {}

    for extension_id, settings in installed.items():
        if not settings.get("enabled", True):
            continue

        manifest = manifests.get(extension_id)
        manifest_config = copy.deepcopy(manifest.config) if manifest else {}
        provided_by = settings.get("provided_by") or (manifest.provided_by if manifest else None) or "local-inline"
        contribution = _deep_merge(manifest_config, settings.get("config", {}))
        if not contribution:
            continue
        _validate_extension_contribution(contribution, label=f"extension '{extension_id}'")
        layer = _deep_merge(layer, contribution)
        enabled_extensions.append(extension_id)
        extension_providers[extension_id] = provided_by
        for path in _flatten_config_paths(contribution):
            extension_path_providers[path] = provided_by

    return layer, enabled_extensions, extension_providers, extension_path_providers


def _read_local_plate_config(repo_root: Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = _plate_path(repo_root)
    if not path.exists():
        return path, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlateConfigError(f"invalid JSON in .plate: {exc}") from exc
    if not isinstance(raw, dict):
        raise PlateConfigError(".plate must contain a top-level object")
    return path, raw


def _resolve_plate_config(repo_root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    path, local = _read_local_plate_config(repo_root)
    present = path.exists()
    if not present:
        return copy.deepcopy(DEFAULT_CONFIG), {
            "path": path,
            "present": False,
            "file_version": None,
            "resolved_version": CURRENT_CONFIG_VERSION,
            "upgrade_available": False,
            "enabled_extensions": [],
            "extension_providers": {},
            "extension_path_providers": {},
            "migration_guidance": [],
        }

    upgraded, migration_guidance, original_version = upgrade_plate_config_dict(local)
    extension_layer, enabled_extensions, extension_providers, extension_path_providers = _resolve_extension_layer(upgraded)
    merged = _deep_merge(DEFAULT_CONFIG, extension_layer)
    merged = _deep_merge(merged, upgraded)
    validate_plate_config(merged, strict=False)

    return merged, {
        "path": path,
        "present": True,
        "file_version": original_version,
        "resolved_version": merged["version"],
        "upgrade_available": original_version != merged["version"],
        "enabled_extensions": enabled_extensions,
        "extension_providers": extension_providers,
        "extension_path_providers": extension_path_providers,
        "migration_guidance": migration_guidance,
    }


def load_plate_config(repo_root: Path | None = None) -> PlateConfig:
    """Load and resolve .plate config with precedence defaults < extensions < local."""

    merged, _meta = _resolve_plate_config(repo_root)
    return PlateConfig.from_dict(merged)


def get_plate_config_report(repo_root: Path | None = None) -> PlateConfigReport:
    """Return effective .plate state for CLI/MCP surfaces."""

    local_path = _plate_path(repo_root).resolve()
    root = str(local_path.parent)
    try:
        config, meta = _resolve_plate_config(local_path.parent)
        return PlateConfigReport(
            repo_root=root,
            path=str(local_path),
            present=meta["present"],
            valid=True,
            source="local_file" if meta["present"] else "defaults",
            config=config,
            file_version=meta["file_version"],
            resolved_version=meta["resolved_version"],
            upgrade_available=meta["upgrade_available"],
            enabled_extensions=meta["enabled_extensions"],
            extension_providers=meta["extension_providers"],
            extension_path_providers=meta["extension_path_providers"],
            migration_guidance=meta["migration_guidance"],
        )
    except PlateConfigError as exc:
        return PlateConfigReport(
            repo_root=root,
            path=str(local_path),
            present=local_path.exists(),
            valid=False,
            source="local_file" if local_path.exists() else "defaults",
            config=copy.deepcopy(DEFAULT_CONFIG),
            file_version=None,
            resolved_version=CURRENT_CONFIG_VERSION,
            errors=[str(exc)],
        )


def _serialize_plate_config(config: PlateConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, PlateConfig):
        return config.to_dict()
    if isinstance(config, dict):
        return copy.deepcopy(config)
    raise TypeError("config must be PlateConfig or dict")


def save_plate_config(
    config: PlateConfig | dict[str, Any],
    repo_root: Path | None = None,
    *,
    overwrite: bool = True,
) -> Path:
    """Write .plate to disk."""

    path = _plate_path(repo_root)
    if path.exists() and not overwrite:
        raise PlateConfigError(".plate already exists; use --force to overwrite")
    payload = _serialize_plate_config(config)
    validate_plate_config(payload, strict=False)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def init_plate_config(repo_root: Path | None = None, *, force: bool = False) -> PlateConfigReport:
    """Create a baseline .plate file if absent (or overwrite with --force)."""

    path = save_plate_config(PlateConfig.from_dict(DEFAULT_CONFIG), repo_root, overwrite=force)
    return get_plate_config_report(path.parent)


def apply_plate_config_upgrade(
    repo_root: Path | None = None,
    *,
    apply: bool = False,
) -> PlateConfigUpgradeReport:
    """Upgrade an existing .plate file to the current schema version."""

    path, local = _read_local_plate_config(repo_root)
    if not path.exists():
        raise PlateConfigError("no .plate file exists; run `gh plate config init --apply` first")

    upgraded, guidance, previous_version = upgrade_plate_config_dict(local)
    changed = upgraded != local
    if apply and changed:
        save_plate_config(upgraded, path.parent, overwrite=True)

    return PlateConfigUpgradeReport(
        repo_root=str(path.parent.resolve()),
        path=str(path.resolve()),
        present=True,
        changed=changed,
        applied=bool(apply and changed),
        previous_version=previous_version,
        current_version=upgraded["version"],
        config=upgraded,
        migration_guidance=guidance,
    )
