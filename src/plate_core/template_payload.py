"""Template payload resolution and manifest loading for PLATE scaffolding assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import fnmatch

import yaml


@dataclass(frozen=True)
class TemplatePayloadManifest:
    """Schema for template payload file selection and classification."""

    schema_version: int
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    copy_to_downstream_globs: tuple[str, ...]
    tool_runtime_only_globs: tuple[str, ...]


def _module_root() -> Path:
    return Path(__file__).resolve().parent


def manifest_path() -> Path:
    """Return the template payload manifest path."""
    return _module_root() / "data" / "template_payload_manifest.yml"


def payload_root() -> Path:
    """Return the checked-in template payload root directory."""
    return _module_root() / "template_payload"


def _as_str_tuple(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a list")
    values: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} entries must be non-empty strings")
        values.append(value)
    return tuple(values)


def load_template_payload_manifest() -> TemplatePayloadManifest:
    """Load and validate template payload manifest."""
    path = manifest_path()
    if not path.exists():
        raise RuntimeError(f"Template payload manifest missing: {path}")

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("Template payload manifest must be a mapping")
    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise ValueError("Template payload manifest schema_version must be 1")

    return TemplatePayloadManifest(
        schema_version=1,
        include_globs=_as_str_tuple(data.get("include_globs", []), "include_globs"),
        exclude_globs=_as_str_tuple(data.get("exclude_globs", []), "exclude_globs"),
        copy_to_downstream_globs=_as_str_tuple(
            data.get("copy_to_downstream_globs", []), "copy_to_downstream_globs"
        ),
        tool_runtime_only_globs=_as_str_tuple(
            data.get("tool_runtime_only_globs", []), "tool_runtime_only_globs"
        ),
    )


def normalize_rel_path(path: str) -> str:
    """Normalize a relative path to POSIX separators and reject path traversal."""
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError(f"Path must be relative: {path}")
    if ".." in normalized.parts:
        raise ValueError(f"Path traversal is not allowed: {path}")
    rel = normalized.as_posix()
    if rel in {".", ""}:
        raise ValueError("Path must not be empty")
    return rel


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if a normalized relative path matches any glob pattern."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def classify_template_file(path: str, manifest: TemplatePayloadManifest) -> str:
    """Classify a file path according to manifest classification rules."""
    rel = normalize_rel_path(path)
    if manifest.exclude_globs and matches_any(rel, manifest.exclude_globs):
        return "exclude"
    if matches_any(rel, manifest.tool_runtime_only_globs):
        return "tool_runtime_only"
    if matches_any(rel, manifest.copy_to_downstream_globs):
        return "copy_to_downstream"
    return "exclude"


def should_include_template_file(path: str, manifest: TemplatePayloadManifest) -> bool:
    """Return True when path is selected for payload inclusion by manifest rules."""
    rel = normalize_rel_path(path)
    if manifest.include_globs and not matches_any(rel, manifest.include_globs):
        return False
    if manifest.exclude_globs and matches_any(rel, manifest.exclude_globs):
        return False
    return True


def resolve_template_source_root(template_repo: str | None = None) -> Path:
    """Resolve source root for scaffold assets.

    Priority:
    1. Explicit template_repo path (for migration/backfill)
    2. Checked-in payload in this repository
    3. Legacy sibling plate_template checkout fallback
    """
    if template_repo:
        explicit = Path(template_repo).resolve()
        if not explicit.exists():
            raise RuntimeError(f"Template repository not found: {explicit}")
        return explicit

    payload = payload_root()
    if payload.exists():
        return payload

    fallback = Path.cwd().resolve().parent / "plate_template"
    if fallback.exists():
        return fallback

    raise RuntimeError(
        "No template source found. Expected either an explicit template_repo, "
        f"a checked-in payload at {payload}, or a sibling plate_template checkout."
    )
