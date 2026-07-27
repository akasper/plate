"""Self-migrate dry-run plan + marker merge executor (#939/#943 / Epic #649).

Plan mode: no pip install, no file writes, no network by default.
Marker merge: dry-run by default; optional explicit apply of PLATES-CORE sections only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from . import __version__ as _INSTALLED_VERSION
from .markers import MarkerParseError, merge_with_diagnostics

_VERSION_RE = re.compile(
    r"(?i)(?:plate-core\s*[=><!~]+\s*|version\s*=\s*)[\"']?v?(\d+\.\d+\.\d+)"
)
_PLAIN_VERSION_RE = re.compile(r"^v?(\d+\.\d+\.\d+)\s*$")

# High-signal paths that self-migrate usually refreshes via import-payload / markers.
_REFRESH_PATHS = (
    "AGENTS.md",
    ".plate",
    ".agentic/skills.yml",
    ".github/labels.yml",
    ".github/workflows",
    "docs/wiki/Goals.md",
    "SPEC.md",
)


def _parse_semver(text: str | None) -> str | None:
    if not text:
        return None
    t = str(text).strip()
    m = _PLAIN_VERSION_RE.match(t)
    if m:
        return m.group(1)
    m = _VERSION_RE.search(t)
    if m:
        return m.group(1)
    return None


def _read_text(path: Path) -> str | None:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def _detect_pin(repo_root: Path) -> dict[str, Any]:
    """Find local plate-core version pin from common adopter files."""
    candidates: list[tuple[str, Path]] = [
        ("PLATE_CORE_VERSION", repo_root / "PLATE_CORE_VERSION"),
        ("VERSION", repo_root / "VERSION"),
        ("gh-plate/VERSION", repo_root / "gh-plate" / "VERSION"),
        ("pyproject.toml", repo_root / "pyproject.toml"),
        ("requirements.txt", repo_root / "requirements.txt"),
    ]
    found: list[dict[str, str]] = []
    primary: str | None = None
    primary_source: str | None = None
    for label, path in candidates:
        text = _read_text(path)
        if text is None:
            continue
        # Prefer first plate-core pin in pyproject/requirements
        ver = None
        if path.name in ("pyproject.toml", "requirements.txt"):
            for line in text.splitlines():
                if "plate-core" in line.lower() or "plate_core" in line.lower():
                    ver = _parse_semver(line)
                    if ver:
                        break
        else:
            ver = _parse_semver(text.splitlines()[0] if text.strip() else text)
        if ver:
            found.append({"source": label, "version": ver, "path": str(path)})
            if primary is None:
                primary = ver
                primary_source = label
    return {
        "version": primary,
        "source": primary_source,
        "pins": found,
    }


def _version_tuple(v: str | None) -> tuple[int, ...] | None:
    if not v:
        return None
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return None


def _compare(a: str | None, b: str | None) -> str:
    """Return equal | behind | ahead | unknown."""
    ta, tb = _version_tuple(a), _version_tuple(b)
    if ta is None or tb is None:
        return "unknown"
    if ta == tb:
        return "equal"
    if ta < tb:
        return "behind"
    return "ahead"


def plan_self_migrate(
    repo_root: str | Path | None = None,
    *,
    target_version: str | None = None,
    include_payload: bool = True,
) -> dict[str, Any]:
    """Build a dry-run self-migrate plan for the local checkout (#939).

    When ``target_version`` is omitted, uses installed plate-core ``__version__``
    as the upgrade target (no network). Pin files are compared to that target.
    """
    root = Path(repo_root or ".").resolve()
    installed = _parse_semver(_INSTALLED_VERSION) or str(_INSTALLED_VERSION)
    pin = _detect_pin(root)
    pin_ver = pin.get("version")
    target = _parse_semver(target_version) if target_version else installed
    if target is None:
        target = installed

    pin_vs_target = _compare(pin_ver, target)
    installed_vs_target = _compare(installed, target)
    pin_vs_installed = _compare(pin_ver, installed)

    drift = pin_vs_target == "behind" or (
        pin_ver is not None and pin_ver != installed and pin_vs_installed != "equal"
    )

    present_refresh: list[dict[str, Any]] = []
    missing_refresh: list[str] = []
    for rel in _REFRESH_PATHS:
        p = root / rel
        if p.exists():
            has_marker = False
            if p.is_file():
                text = _read_text(p) or ""
                has_marker = "PLATES-CORE" in text or "PLATES-CORE:" in text
            present_refresh.append(
                {
                    "path": rel,
                    "kind": "dir" if p.is_dir() else "file",
                    "has_plates_core_markers": has_marker,
                }
            )
        else:
            missing_refresh.append(rel)

    steps: list[dict[str, Any]] = [
        {
            "id": "1_status",
            "description": "Review this plan (gh plate self-migrate --plan --json)",
            "dry_run_only": True,
        },
    ]
    if pin_vs_target == "behind" or installed_vs_target == "behind":
        steps.append(
            {
                "id": "2_upgrade_runtime",
                "description": (
                    f"Upgrade plate-core to {target} "
                    f"(pip install 'plate-core=={target}' or refresh gh-plate pin)"
                ),
                "dry_run_only": False,
                "requires_user_approval": True,
            }
        )
    if pin_ver and pin_ver != target:
        steps.append(
            {
                "id": "3_align_pin_files",
                "description": (
                    f"Align pin files ({pin.get('source')}) to {target} "
                    "when using VERSION/PLATE_CORE_VERSION"
                ),
                "dry_run_only": False,
                "requires_user_approval": True,
            }
        )
    if include_payload:
        steps.append(
            {
                "id": "4_import_payload",
                "description": (
                    "gh plate import-payload --dry-run --strategy conservative --json "
                    "then --apply after review (preserves local customizations)"
                ),
                "dry_run_only": False,
                "requires_user_approval": True,
            }
        )
    steps.append(
        {
            "id": "5_marker_aware_review",
            "description": (
                "gh plate self-migrate --merge-markers --upstream-dir <upstream> --json "
                "(optional --apply-markers after review); preserve local outside markers"
            ),
            "dry_run_only": True,
        }
    )
    steps.append(
        {
            "id": "6_verify",
            "description": "gh plate health; gh plate adopt --json; gh plate config validate",
            "dry_run_only": True,
        }
    )

    risk = "low"
    if pin_vs_target == "behind" or installed_vs_target == "behind":
        risk = "medium"
    if any(p.get("has_plates_core_markers") for p in present_refresh):
        # marker merge needs care but still medium not high
        risk = "medium" if risk == "low" else risk

    next_cmd = "gh plate self-migrate --plan --json"
    if include_payload and drift:
        next_cmd = (
            "gh plate import-payload --dry-run --strategy conservative --json"
        )
    elif pin_vs_target == "behind":
        next_cmd = f"pip install 'plate-core=={target}'"

    return {
        "ok": True,
        "mode": "dry_run_plan",
        "repo_root": str(root),
        "installed_version": installed,
        "pin": pin,
        "target_version": target,
        "comparisons": {
            "pin_vs_target": pin_vs_target,
            "installed_vs_target": installed_vs_target,
            "pin_vs_installed": pin_vs_installed,
        },
        "drift": drift,
        "risk": risk,
        "steps": steps,
        "refresh_paths_present": present_refresh,
        "refresh_paths_missing": missing_refresh,
        "next_command": next_cmd,
        "auto_apply": False,
        "note": (
            "Plan only — no pip install, file writes, or network. "
            "Human/agent executes steps after review (#649)."
        ),
        "related_issues": ["#939", "#649", "#633", "#615", "#654"],
        "ask_user_question": {
            "question": (
                f"Self-migrate plan ready (target {target}, drift={drift}). Proceed?"
            ),
            "options": [
                {
                    "label": "Import-payload dry-run",
                    "description": "Conservative payload refresh",
                },
                {
                    "label": "Upgrade plate-core pin",
                    "description": f"pip install plate-core=={target}",
                },
                {
                    "label": "Marker merge plan",
                    "description": "gh plate self-migrate --merge-markers --json",
                },
                {"label": "Health only", "description": "gh plate health"},
                {"label": "Defer", "description": "Keep plan artifact only"},
            ],
        },
    }


def _default_marker_paths(repo_root: Path) -> list[str]:
    """Prefer high-signal files that actually exist and contain markers."""
    out: list[str] = []
    for rel in _REFRESH_PATHS:
        p = repo_root / rel
        if not p.is_file():
            continue
        text = _read_text(p) or ""
        if "PLATES-CORE" in text:
            out.append(rel)
    if not out and (repo_root / "AGENTS.md").is_file():
        out.append("AGENTS.md")
    return out


def plan_marker_merge(
    repo_root: str | Path | None = None,
    *,
    paths: list[str] | None = None,
    upstream_root: str | Path | None = None,
    upstream_texts: Mapping[str, str] | None = None,
    base_texts: Mapping[str, str] | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan (and optionally apply) PLATES-CORE sectional merges (#943 / #649).

    For each path: 3-way merge via ``merge_with_diagnostics``.
    When base is omitted for a path, base defaults to local content so unedited
    marker blocks accept upstream while content outside markers is preserved
    from local (and local marker customizations only win when a true base is
    supplied that differs from local).

    Dry-run by default (``apply=False``). Never performs network I/O.
    Upstream content comes from ``upstream_root`` files and/or ``upstream_texts``.
    """
    root = Path(repo_root or ".").resolve()
    up_root = Path(upstream_root).resolve() if upstream_root else None
    up_map = dict(upstream_texts or {})
    base_map = dict(base_texts or {})
    rels = list(paths) if paths else _default_marker_paths(root)

    files: list[dict[str, Any]] = []
    would_write = 0
    written = 0
    errors: list[str] = []

    for rel in rels:
        local_path = root / rel
        entry: dict[str, Any] = {
            "path": rel,
            "action": "skip",
            "changed": False,
            "preserved_local_sections": [],
            "warnings": [],
            "applied": False,
        }
        if not local_path.is_file():
            entry["action"] = "missing_local"
            entry["warnings"] = [f"Local file not found: {rel}"]
            files.append(entry)
            continue

        local = _read_text(local_path) or ""
        upstream: str | None = up_map.get(rel)
        if upstream is None and up_root is not None:
            upstream = _read_text(up_root / rel)
        if upstream is None:
            entry["action"] = "missing_upstream"
            entry["warnings"] = [
                "No upstream text (pass --upstream-dir or upstream_texts)"
            ]
            files.append(entry)
            continue

        base = base_map.get(rel, local)
        try:
            result = merge_with_diagnostics(base, local, upstream)
        except MarkerParseError as exc:
            entry["action"] = "parse_error"
            entry["warnings"] = [str(exc)]
            errors.append(f"{rel}: {exc}")
            files.append(entry)
            continue

        merged = result.text
        changed = merged != local
        entry["preserved_local_sections"] = list(result.preserved_local_sections)
        entry["warnings"] = list(result.warnings)
        entry["changed"] = changed
        if not changed:
            entry["action"] = "unchanged"
        else:
            entry["action"] = "update_markers"
            would_write += 1
            if apply:
                try:
                    local_path.write_text(merged, encoding="utf-8")
                    entry["applied"] = True
                    written += 1
                except OSError as exc:
                    entry["action"] = "write_error"
                    entry["warnings"] = entry["warnings"] + [str(exc)]
                    errors.append(f"{rel}: write failed: {exc}")
            else:
                # Dry-run preview: truncated unified-ish note
                entry["preview_len"] = len(merged)
        files.append(entry)

    mode = "apply" if apply else "dry_run"
    return {
        "ok": len(errors) == 0,
        "mode": mode,
        "repo_root": str(root),
        "upstream_root": str(up_root) if up_root else None,
        "paths": rels,
        "files": files,
        "would_write": would_write,
        "written": written,
        "auto_apply": False,
        "apply_requested": apply,
        "errors": errors,
        "note": (
            "Marker merge only touches PLATES-CORE sections (via merge_with_diagnostics). "
            "Outside-marker local content is preserved. Dry-run unless apply=true (#943)."
        ),
        "related_issues": ["#943", "#649", "#939", "#633", "#654"],
        "next_command": (
            "gh plate self-migrate --merge-markers --upstream-dir <upstream> --json"
            if not apply
            else "gh plate health"
        ),
    }
