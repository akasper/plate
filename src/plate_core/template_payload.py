"""Template payload resolution and manifest loading for PLATE scaffolding assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import fnmatch
from typing import Any

import yaml

# Conflict strategies for path_rules (#617)
VALID_ON_CONFLICT = frozenset(
    {
        "skip",
        "overwrite",
        "conflict",
        "install_as",  # write payload to install_as path; leave existing
        "preserve_existing",  # alias of skip with explicit reason
    }
)


@dataclass(frozen=True)
class PathConflictRule:
    """Per-path conflict/adoption rule (#617)."""

    globs: tuple[str, ...]
    on_conflict: str
    install_as: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "globs": list(self.globs),
            "on_conflict": self.on_conflict,
            "install_as": self.install_as,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TemplatePayloadManifest:
    """Schema for template payload file selection and classification."""

    schema_version: int
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    copy_to_downstream_globs: tuple[str, ...]
    tool_runtime_only_globs: tuple[str, ...]
    path_rules: tuple[PathConflictRule, ...] = field(default_factory=tuple)


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


def _parse_path_rules(raw: object) -> tuple[PathConflictRule, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("path_rules must be a list")
    rules: list[PathConflictRule] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"path_rules[{i}] must be a mapping")
        globs = item.get("globs") or item.get("glob")
        if isinstance(globs, str):
            globs_t = (globs,)
        else:
            globs_t = _as_str_tuple(globs or [], f"path_rules[{i}].globs")
        if not globs_t:
            raise ValueError(f"path_rules[{i}].globs must be non-empty")
        on_conflict = str(item.get("on_conflict") or item.get("conflict_strategy") or "skip")
        if on_conflict not in VALID_ON_CONFLICT:
            raise ValueError(
                f"path_rules[{i}].on_conflict must be one of {sorted(VALID_ON_CONFLICT)}"
            )
        install_as = item.get("install_as")
        if install_as is not None:
            install_as = normalize_rel_path(str(install_as))
        if on_conflict == "install_as" and not install_as:
            raise ValueError(f"path_rules[{i}]: install_as required when on_conflict=install_as")
        rules.append(
            PathConflictRule(
                globs=globs_t,
                on_conflict=on_conflict,
                install_as=install_as,
                reason=str(item.get("reason") or ""),
            )
        )
    return tuple(rules)


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
    # v1 = base globs; v2 adds path_rules (v1 may still carry optional path_rules)
    if schema_version not in (1, 2):
        raise ValueError("Template payload manifest schema_version must be 1 or 2")

    return TemplatePayloadManifest(
        schema_version=int(schema_version),
        include_globs=_as_str_tuple(data.get("include_globs", []), "include_globs"),
        exclude_globs=_as_str_tuple(data.get("exclude_globs", []), "exclude_globs"),
        copy_to_downstream_globs=_as_str_tuple(
            data.get("copy_to_downstream_globs", []), "copy_to_downstream_globs"
        ),
        tool_runtime_only_globs=_as_str_tuple(
            data.get("tool_runtime_only_globs", []), "tool_runtime_only_globs"
        ),
        path_rules=_parse_path_rules(data.get("path_rules")),
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


def match_path_rule(path: str, manifest: TemplatePayloadManifest) -> PathConflictRule | None:
    """Return the first path_rules entry matching path (declaration order)."""
    rel = normalize_rel_path(path)
    for rule in manifest.path_rules:
        if matches_any(rel, rule.globs):
            return rule
    return None


def resolve_conflict_plan(
    path: str,
    *,
    dest_exists: bool,
    identical: bool,
    strategy: str,
    manifest: TemplatePayloadManifest,
) -> dict[str, Any]:
    """Plan create/skip/conflict/overwrite/create_as for one payload path (#617).

    Greenfield (missing dest): always create at original path.
    On conflict: path_rules may override global strategy (esp. install_as for ci.yml).
    Global ``force`` still overwrites original path unless rule is never needed.
    """
    rel = normalize_rel_path(path)
    rule = match_path_rule(rel, manifest)
    strat = (strategy or "safe").lower()

    if not dest_exists:
        return {
            "path": rel,
            "target_path": rel,
            "action": "create",
            "detail": "missing at target",
            "rule": rule.to_dict() if rule else None,
        }

    if identical:
        return {
            "path": rel,
            "target_path": rel,
            "action": "skip",
            "detail": "identical content",
            "rule": rule.to_dict() if rule else None,
        }

    # Differing existing content
    if rule and rule.on_conflict == "install_as" and rule.install_as:
        return {
            "path": rel,
            "target_path": rule.install_as,
            "action": "create_as",
            "detail": (
                rule.reason
                or f"existing differs; install payload as {rule.install_as} (preserve {rel})"
            ),
            "rule": rule.to_dict(),
        }

    if rule and rule.on_conflict in ("skip", "preserve_existing") and strat != "force":
        return {
            "path": rel,
            "target_path": rel,
            "action": "skip",
            "detail": rule.reason or "path_rule: preserve existing",
            "rule": rule.to_dict(),
        }

    if rule and rule.on_conflict == "overwrite":
        return {
            "path": rel,
            "target_path": rel,
            "action": "overwrite",
            "detail": rule.reason or "path_rule: safe-overwrite",
            "rule": rule.to_dict(),
        }

    if rule and rule.on_conflict == "conflict" and strat != "force":
        return {
            "path": rel,
            "target_path": rel,
            "action": "conflict",
            "detail": rule.reason or "path_rule: prompt-or-skip / conflict",
            "rule": rule.to_dict(),
        }

    if strat == "force":
        return {
            "path": rel,
            "target_path": rel,
            "action": "overwrite",
            "detail": "existing differs; force overwrites",
            "rule": rule.to_dict() if rule else None,
        }

    if strat == "conservative":
        return {
            "path": rel,
            "target_path": rel,
            "action": "conflict",
            "detail": "existing differs; conservative never overwrites",
            "rule": rule.to_dict() if rule else None,
        }

    return {
        "path": rel,
        "target_path": rel,
        "action": "skip",
        "detail": "exists at target (safe strategy skips)",
        "rule": rule.to_dict() if rule else None,
    }


def resolve_template_source_root(template_repo: str | None = None) -> Path:
    """Resolve source root for scaffold assets.

    Priority:
    1. Explicit template_repo path (for migration/backfill)
    2. Checked-in payload in this repository
    3. Legacy sibling plate_template checkout fallback
    """
    source_root, _source_kind = resolve_template_source(template_repo)
    return source_root


def resolve_template_source(template_repo: str | None = None) -> tuple[Path, str]:
    """Resolve scaffold source root and return source provenance.

    Returns:
        (path, source_kind)
        source_kind is one of:
        - "explicit_path"
        - "package_payload"
        - "legacy_sibling_fallback"
    """
    if template_repo:
        explicit = Path(template_repo).resolve()
        if not explicit.exists():
            raise RuntimeError(f"Template repository not found: {explicit}")
        return explicit, "explicit_path"

    payload = payload_root()
    if payload.exists():
        return payload, "package_payload"

    fallback = Path.cwd().resolve().parent / "plate_template"
    if fallback.exists():
        return fallback, "legacy_sibling_fallback"

    raise RuntimeError(
        "No template source found. Expected either an explicit template_repo, "
        f"a checked-in payload at {payload}, or a sibling plate_template checkout."
    )
