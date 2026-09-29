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

# Plate-owned doc subdirectories under template payload docs/ (PLATE scaffolding)
PLATE_DOCS_SUBDIRS: frozenset[str] = frozenset(
    {
        "adr",
        "audits",
        "bootstrap",
        "design",
        "marketing",
        "migration",
        "research",
        "wiki",
    }
)

# Plate-owned doc files at docs/ root (from template payload).
# Filename alone is not ownership: product repos commonly ship docs/README.md.
# A root file counts as PLATE only when its content contains every marker below.
PLATE_DOCS_ROOT_FILES: frozenset[str] = frozenset(
    {
        "README.md",
        "playwright-e2e-guide.md",
    }
)

PLATE_DOCS_ROOT_CONTENT_MARKERS: dict[str, tuple[str, ...]] = {
    "README.md": ("# Documentation Index", "playwright-e2e-guide.md"),
    "playwright-e2e-guide.md": (
        "# Playwright E2E Testing & Demo GIF Generation Guide",
    ),
}


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
    
    # Suggest namespaced install paths when applicable
    suggested = rel
    if rel.startswith("scripts/"):
        suggested = namespace_script_path(rel)
    elif rel.startswith("docs/"):
        suggested = namespace_docs_path(rel)
    
    return {
        "ok": True,
        "path": rel,
        "included": should_include_template_file(rel, m),
        "classification": classify_template_file(rel, m),
        "path_rule": rule.to_dict() if rule else None,
        "suggested_install_path": suggested,
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


def namespace_docs_path(rel: str) -> str:
    """Map docs/* → docs/plate/* when namespacing (#1015)."""
    if rel.startswith("docs/plate/"):
        return rel
    if rel.startswith("docs/"):
        return "docs/plate/" + rel[len("docs/") :]
    return rel


def is_plate_owned_root_doc(path: Path) -> bool:
    """True when ``path`` is a packaged PLATE docs/-root file, not adopter content.

    ``docs/README.md`` and ``docs/playwright-e2e-guide.md`` are common product
    filenames. Ownership requires the template content markers, not the name.
    """
    markers = PLATE_DOCS_ROOT_CONTENT_MARKERS.get(path.name)
    if not markers:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:8000]
    except OSError:
        return False
    return all(marker in head for marker in markers)


def should_namespace_docs(target: Path) -> bool:
    """True when target already has product docs (not only PLATE scaffolding) (#1015)."""
    docs = Path(target) / "docs"
    if not docs.is_dir():
        return False
    for path in docs.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(docs).parts
        except ValueError:
            continue
        if not rel_parts:
            continue
        # Skip if under docs/plate/ (already namespaced PLATE docs)
        if rel_parts[0] == "plate":
            continue
        # Skip if under a known PLATE scaffolding subdir at top level
        if len(rel_parts) >= 1 and rel_parts[0] in PLATE_DOCS_SUBDIRS:
            continue
        # Skip packaged PLATE root docs. Same filename with other content is product.
        if len(rel_parts) == 1 and is_plate_owned_root_doc(path):
            continue
        # Any other path under docs/ is treated as product docs collision
        return True
    return False


def rewrite_docs_refs(text: str) -> str:
    """Rewrite docs/* → docs/plate/* in text files (#1015)."""
    out = text
    # Rewrite common patterns for docs/ paths
    # Pattern 1: docs/subdir/ (most common)
    for subdir in sorted(PLATE_DOCS_SUBDIRS, key=len, reverse=True):
        out = out.replace(f"docs/{subdir}/", f"docs/plate/{subdir}/")
        out = out.replace(f"`docs/{subdir}/", f"`docs/plate/{subdir}/")
    # Pattern 2: docs/<filename> at root (less common but present)
    # Be more careful here to avoid false positives - look for .md extension
    out = out.replace("docs/README.md", "docs/plate/README.md")
    out = out.replace("`docs/README.md", "`docs/plate/README.md")
    # Pattern 3: Generic docs/ in paths (with trailing slash to avoid partial matches)
    # Only replace when it looks like a path reference, not prose
    import re
    # Replace `docs/` (backtick-wrapped) with `docs/plate/`
    out = re.sub(r'`docs/([a-zA-Z0-9_\-]+\.md)', r'`docs/plate/\1', out)
    return out
    return out
