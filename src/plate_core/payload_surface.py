"""Payload discoverability surfaces for agents and adopters (#621).

CLI: ``gh plate payload list|root|manifest|classify``
MCP: ``plate_payload_*``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .template_payload import (
    classify_template_file,
    load_template_payload_manifest,
    match_path_rule,
    payload_root,
    resolve_template_source,
    should_include_template_file,
)

# Plate-owned scripts under template payload scripts/ (not project product scripts)
PLATE_SCRIPT_BASENAMES: frozenset[str] = frozenset(
    {
        "validate_plate_repo.sh",
        "ValidatePlateRepo.ps1",
        "bootstrap_github.sh",
        "BootstrapGitHub.ps1",
        "check_toolchain.sh",
        "CheckToolchain.ps1",
        "question_batch.sh",
        "QuestionBatch.ps1",
        "e2e-record.sh",
        "e2e-record.ps1",
        "gif-from-video.sh",
        "gif-from-video.ps1",
        "dev-server.js",
        "README.md",
    }
)


def resolve_payload_root(template_repo: str | None = None) -> dict[str, Any]:
    """Resolve package/explicit payload root for agents."""
    root, kind = resolve_template_source(template_repo)
    return {
        "ok": True,
        "path": str(root),
        "source_kind": kind,
        "package_payload_path": str(payload_root()),
    }


def list_payload_files(
    template_repo: str | None = None,
    *,
    include_excluded: bool = False,
) -> dict[str, Any]:
    """List manifest-filtered payload files with classification + path_rules."""
    root, kind = resolve_template_source(template_repo)
    manifest = load_template_payload_manifest()
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        included = should_include_template_file(rel, manifest)
        if not included and not include_excluded:
            continue
        classification = classify_template_file(rel, manifest)
        rule = match_path_rule(rel, manifest)
        files.append(
            {
                "path": rel,
                "included": included,
                "classification": classification,
                "path_rule": rule.to_dict() if rule else None,
                "is_plate_script": rel.startswith("scripts/")
                and Path(rel).name in PLATE_SCRIPT_BASENAMES,
            }
        )
    return {
        "ok": True,
        "source_kind": kind,
        "template_root": str(root),
        "count": len(files),
        "files": files,
    }


def show_manifest() -> dict[str, Any]:
    """Return loaded manifest as JSON-friendly dict."""
    m = load_template_payload_manifest()
    return {
        "ok": True,
        "schema_version": m.schema_version,
        "include_globs": list(m.include_globs),
        "exclude_globs": list(m.exclude_globs),
        "copy_to_downstream_globs": list(m.copy_to_downstream_globs),
        "tool_runtime_only_globs": list(m.tool_runtime_only_globs),
        "path_rules": [r.to_dict() for r in m.path_rules],
    }


def classify_path(path: str, template_repo: str | None = None) -> dict[str, Any]:
    """Classify a relative path against the manifest + path_rules."""
    from .template_payload import normalize_rel_path

    rel = normalize_rel_path(path)
    m = load_template_payload_manifest()
    rule = match_path_rule(rel, m)
    return {
        "ok": True,
        "path": rel,
        "included": should_include_template_file(rel, m),
        "classification": classify_template_file(rel, m),
        "path_rule": rule.to_dict() if rule else None,
        "suggested_install_path": (
            namespace_script_path(rel) if rel.startswith("scripts/") else rel
        ),
        "is_plate_script": rel.startswith("scripts/")
        and Path(rel).name in PLATE_SCRIPT_BASENAMES,
    }


def namespace_script_path(rel: str) -> str:
    """Map scripts/foo → scripts/plate/foo when namespacing (#621)."""
    if rel.startswith("scripts/plate/"):
        return rel
    if rel.startswith("scripts/"):
        return "scripts/plate/" + rel[len("scripts/") :]
    return rel


def should_namespace_scripts(target: Path) -> bool:
    """True when target already has product scripts (not only PLATE helpers)."""
    scripts = Path(target) / "scripts"
    if not scripts.is_dir():
        return False
    for path in scripts.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(scripts).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] == "plate":
            continue
        # Top-level known PLATE helper already installed at scripts/<name>
        if len(rel_parts) == 1 and path.name in PLATE_SCRIPT_BASENAMES:
            continue
        # Any other path under scripts/ is treated as product collision risk
        return True
    return False


def rewrite_workflow_script_refs(text: str) -> str:
    """Rewrite scripts/<plate-script> → scripts/plate/<plate-script> in workflow bodies."""
    out = text
    for name in sorted(PLATE_SCRIPT_BASENAMES, key=len, reverse=True):
        if name == "README.md":
            continue
        out = out.replace(f"scripts/{name}", f"scripts/plate/{name}")
        out = out.replace(f"./scripts/{name}", f"./scripts/plate/{name}")
    return out
