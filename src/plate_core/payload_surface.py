"""Payload discoverability surfaces for agents and adopters (#621).

CLI: ``gh plate payload list|root|manifest|classify``
MCP: ``plate_payload_*``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .plate_config import PLATFORM_POSIX, PLATFORM_WINDOWS
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


def plate_script_flavor(rel: str) -> str | None:
    """Return ``sh`` or ``ps1`` for a PLATE-owned script twin, else None.

    Adopter-owned scripts and non-script payload files (README, dev-server.js)
    are not flavors that import filtering drops.
    """
    name = Path(rel).name
    if name not in PLATE_SCRIPT_BASENAMES:
        return None
    if name.endswith(".ps1"):
        return "ps1"
    if name.endswith(".sh"):
        return "sh"
    return None


def plate_script_included(rel: str, platform: str) -> bool:
    """Whether a payload path is copied for ``platform``.

    ``posix`` omits PLATE-owned ``.ps1`` twins. ``windows`` omits PLATE-owned
    ``.sh`` twins. ``posix-and-windows`` copies both. Other files always copy.
    """
    flavor = plate_script_flavor(rel)
    if flavor is None:
        return True
    if platform == PLATFORM_POSIX:
        return flavor != "ps1"
    if platform == PLATFORM_WINDOWS:
        return flavor != "sh"
    return True


def filter_plate_scripts(rel_paths: list[str], platform: str) -> tuple[list[str], list[str]]:
    """Split manifest paths into those copied and those omitted for ``platform``."""
    kept: list[str] = []
    omitted: list[str] = []
    for rel in rel_paths:
        if plate_script_included(rel, platform):
            kept.append(rel)
        else:
            omitted.append(rel)
    return kept, omitted


_WINDOWS_DOC_SCRIPTS = (
    ("e2e-record.sh", "e2e-record.ps1"),
    ("gif-from-video.sh", "gif-from-video.ps1"),
    ("validate_plate_repo.sh", "ValidatePlateRepo.ps1"),
    ("bootstrap_github.sh", "BootstrapGitHub.ps1"),
    ("check_toolchain.sh", "CheckToolchain.ps1"),
    ("question_batch.sh", "QuestionBatch.ps1"),
)

_WINDOWS_DOC_FLAGS = (
    ("--skip-gif", "-SkipGif"),
    ("--headed", "-Headed"),
    ("--debug", "-Debug"),
    ("--help", "-Help"),
    ("--quality", "-Quality"),
    ("--start", "-Start"),
    ("--duration", "-Duration"),
    ("--fps", "-Fps"),
    ("--width", "-Width"),
)

# Longer flags first so a short token is not taken out of a longer one.
_WINDOWS_BOOTSTRAP_FLAGS = (
    ("--skip-runtime-toolchain-check", "-SkipRuntimeToolchainCheck"),
    ("--set-delete-branch-on-merge", "-SetDeleteBranchOnMerge"),
    ("--remove-default-labels", "-RemoveDefaultLabels"),
    ("--protect-branch", "-ProtectBranch"),
    ("--owner-handle", "-OwnerHandle"),
    ("--local-repo", "-LocalRepo"),
    ("--init-wiki", "-InitWiki"),
    ("--repo", "-Repo"),
)


def _rewrite_windows_doc_script_refs(text: str, *, namespaced: bool) -> str:
    """Point copied docs at the PowerShell helpers a windows copy ships.

    ``./scripts/e2e-record.sh`` becomes ``pwsh -File ./scripts/e2e-record.ps1``.
    ``bash scripts/bootstrap_github.sh`` keeps its arguments and changes the
    wrapper to ``pwsh -File``. A namespaced copy uses ``scripts/plate/``.
    Shell long options on those command lines become the PowerShell parameter
    names. Prose that only mentions a flag is left unchanged.
    """
    dest_prefix = "scripts/plate/" if namespaced else "scripts/"
    pairs: list[tuple[str, str]] = []
    for sh_name, ps_name in _WINDOWS_DOC_SCRIPTS:
        ps_rel = f"{dest_prefix}{ps_name}"
        ps_win = ps_rel.replace("/", "\\")
        for folder in ("scripts/plate/", "scripts/"):
            sh_rel = f"{folder}{sh_name}"
            sh_win = sh_rel.replace("/", "\\")
            # bash wrappers before bare paths, or `bash scripts/foo.sh`
            # becomes `bash scripts/Foo.ps1` and never invokes PowerShell.
            pairs.append((f"bash ./{sh_rel}", f"pwsh -File ./{ps_rel}"))
            pairs.append((f"bash {sh_rel}", f"pwsh -File {ps_rel}"))
            pairs.append((f"bash .\\{sh_win}", f"pwsh -File .\\{ps_win}"))
            pairs.append((f"bash {sh_win}", f"pwsh -File {ps_win}"))
            pairs.append((f"./{sh_rel}", f"pwsh -File ./{ps_rel}"))
            pairs.append((f".\\{sh_win}", f"pwsh -File .\\{ps_win}"))
            pairs.append((sh_rel, ps_rel))
            pairs.append((sh_win, ps_win))
    for old, new in sorted(pairs, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(old, new)
    # Bare names such as `e2e-record.sh` in prose, after path forms are gone.
    for sh_name, ps_name in _WINDOWS_DOC_SCRIPTS:
        text = text.replace(sh_name, ps_name)
    lines: list[str] = []
    for line in text.split("\n"):
        if "e2e-record.ps1" in line or "gif-from-video.ps1" in line:
            for old, new in _WINDOWS_DOC_FLAGS:
                line = line.replace(old, new)
        if "BootstrapGitHub.ps1" in line:
            for old, new in _WINDOWS_BOOTSTRAP_FLAGS:
                line = line.replace(old, new)
        lines.append(line)
    return "\n".join(lines)


def prepare_copied_text(rel: str, text: str, platform: str, *, namespaced: bool) -> str:
    """Adjust copied GitHub metadata for script namespacing and windows CI.

    Matches the template test job with either LF or CRLF and writes the same
    newline style back, so a Windows checkout still flips ``runs-on``.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    if namespaced and _copies_plate_script_refs(rel):
        text = rewrite_workflow_script_refs(text)
    if platform == PLATFORM_WINDOWS and Path(rel).name == "package.json":
        recorder = (
            "scripts/plate/e2e-record.ps1" if namespaced else "scripts/e2e-record.ps1"
        )
        text = text.replace(
            "bash scripts/plate/e2e-record.sh",
            f"pwsh -File {recorder}",
        )
        text = text.replace("bash scripts/e2e-record.sh", f"pwsh -File {recorder}")
    if platform != PLATFORM_WINDOWS:
        return text.replace("\n", newline) if newline != "\n" else text
    if rel.endswith(".md") and not (
        rel.startswith(".github/workflows/") or rel.endswith("copilot-instructions.md")
    ):
        text = _rewrite_windows_doc_script_refs(text, namespaced=namespaced)
        return text.replace("\n", newline) if newline != "\n" else text
    if not (rel.startswith(".github/workflows/") or rel.endswith("copilot-instructions.md")):
        return text.replace("\n", newline) if newline != "\n" else text
    ps_name = (
        "scripts/plate/ValidatePlateRepo.ps1"
        if namespaced
        else "scripts/ValidatePlateRepo.ps1"
    )
    bash_name = (
        "scripts/plate/validate_plate_repo.sh"
        if namespaced
        else "scripts/validate_plate_repo.sh"
    )
    text = text.replace(f"bash {bash_name} .", f"pwsh -File {ps_name} -Root .")
    if namespaced:
        text = text.replace(
            "bash scripts/validate_plate_repo.sh .",
            f"pwsh -File {ps_name} -Root .",
        )
    if rel.endswith("ci.yml"):
        text = text.replace(
            "  test:\n    needs: labels\n    runs-on: ubuntu-latest\n",
            "  test:\n    needs: labels\n    runs-on: windows-latest\n",
            1,
        )
    if rel.endswith("test-e2e.yml"):
        text = _rewrite_windows_gif_job(text, namespaced=namespaced)
    if rel.endswith(".md"):
        text = _rewrite_windows_doc_script_refs(text, namespaced=namespaced)
    if newline != "\n":
        text = text.replace("\n", newline)
    return text


def _rewrite_windows_gif_job(text: str, *, namespaced: bool) -> str:
    """Point process-gifs at the PowerShell helper a windows copy actually ships.

    The job stays on ubuntu-latest: its size checks are bash, and GitHub's
    Ubuntu image provides pwsh. The shell twin is not copied for windows, so
    a missing helper or a missing pwsh fails the step instead of being hidden
    by ``|| true``. Per-video conversion errors stay non-fatal.
    """
    gif = "scripts/plate/gif-from-video.ps1" if namespaced else "scripts/gif-from-video.ps1"
    shell = "scripts/plate/gif-from-video.sh" if namespaced else "scripts/gif-from-video.sh"
    old = f'              ./{shell} "$video" "$gif_name" --quality medium || true'
    if old not in text:
        return text
    checked = (
        f'              gif_script="./{gif}"\n'
        '              if [[ ! -f "$gif_script" ]]; then\n'
        '                echo "Required GIF script is missing: $gif_script" >&2\n'
        "                exit 1\n"
        "              fi\n"
        "              if ! command -v pwsh >/dev/null 2>&1; then\n"
        '                echo "pwsh is required to run $gif_script" >&2\n'
        "                exit 1\n"
        "              fi\n"
        '              pwsh -File "$gif_script" -InputVideo "$video" -OutputGif "$gif_name" -Quality medium || true'
    )
    text = text.replace(old, checked, 1)
    anchor = (
        "      - name: Download test videos\n"
        "        uses: actions/download-artifact@v4\n"
        "        with:\n"
        "          name: playwright-videos\n"
        "\n"
        "      - name: Convert videos to GIFs\n"
    )
    install = (
        "      - name: Download test videos\n"
        "        uses: actions/download-artifact@v4\n"
        "        with:\n"
        "          name: playwright-videos\n"
        "\n"
        "      - name: Install ffmpeg\n"
        "        run: sudo apt-get update && sudo apt-get install -y ffmpeg\n"
        "\n"
        "      - name: Convert videos to GIFs\n"
    )
    if anchor in text:
        text = text.replace(anchor, install, 1)
    return text

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


def _copies_plate_script_refs(rel: str) -> bool:
    """True when namespacing should retarget PLATE script paths inside ``rel``."""
    if rel.startswith(".github/") or Path(rel).name == "package.json":
        return True
    return rel.startswith("scripts/") and Path(rel).name in PLATE_SCRIPT_BASENAMES


def rewrite_workflow_script_refs(text: str) -> str:
    """Rewrite PLATE script paths to ``scripts/plate/`` (slash or backslash)."""
    out = text
    for name in sorted(PLATE_SCRIPT_BASENAMES, key=len, reverse=True):
        if name == "README.md":
            continue
        out = out.replace(f"scripts/{name}", f"scripts/plate/{name}")
        out = out.replace(f"./scripts/{name}", f"./scripts/plate/{name}")
        out = out.replace(f"scripts\\{name}", f"scripts\\plate\\{name}")
        out = out.replace(f".\\scripts\\{name}", f".\\scripts\\plate\\{name}")
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
