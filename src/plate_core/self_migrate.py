"""Self-migrate dry-run plan + marker merge + optional upstream resolve + verify (#939/#943/#945/#965 / Epic #649).

Plan mode: no pip install, no file writes, no network by default.
Marker merge: dry-run by default; optional explicit apply of PLATES-CORE sections only.
Upstream resolve: injectable fetcher; network only when allow_network=True.
Verify mode: offline post-migrate checks (drift, adoption readiness, .plate validity).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

from . import __version__ as _INSTALLED_VERSION
from .markers import MarkerParseError, merge_with_diagnostics

# Callable returns raw text or mapping with a version field; never required at import time.
UpstreamFetcher = Callable[[], Any]

_PYPI_JSON_URL = "https://pypi.org/pypi/plate-core/json"

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


def _extract_version_from_payload(payload: Any) -> str | None:
    """Parse a version from PyPI JSON, plain text, or mapping."""
    if payload is None:
        return None
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8", errors="replace")
        except Exception:
            return None
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        # Prefer JSON info.version when payload looks like PyPI JSON
        if text.startswith("{"):
            try:
                data = json.loads(text)
                return _extract_version_from_payload(data)
            except json.JSONDecodeError:
                pass
        return _parse_semver(text.splitlines()[0])
    if isinstance(payload, Mapping):
        info = payload.get("info")
        if isinstance(info, Mapping) and info.get("version"):
            return _parse_semver(str(info["version"]))
        if payload.get("version"):
            return _parse_semver(str(payload["version"]))
        # releases map: pick highest semver key if present
        releases = payload.get("releases")
        if isinstance(releases, Mapping) and releases:
            best: str | None = None
            for key in releases.keys():
                ver = _parse_semver(str(key))
                if ver is None:
                    continue
                if best is None or _compare(ver, best) == "ahead":
                    best = ver
            return best
    return None


def default_pypi_fetcher(timeout: float = 5.0) -> Any:
    """Fetch plate-core PyPI JSON (network). Used only when allow_network=True."""
    req = urllib.request.Request(
        _PYPI_JSON_URL,
        headers={"Accept": "application/json", "User-Agent": "plate-core-self-migrate"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 — fixed HTTPS URL
        return resp.read()


def resolve_upstream_version(
    *,
    allow_network: bool = False,
    fetcher: UpstreamFetcher | None = None,
    package: str = "plate-core",
) -> dict[str, Any]:
    """Resolve an upstream plate-core version (#945).

    Default is offline: without ``fetcher`` and without ``allow_network``, returns
    ok with version=None and source=offline_default (no network).
    When ``fetcher`` is provided it is always used (tests inject).
    When ``allow_network`` is True and no fetcher, uses :func:`default_pypi_fetcher`.
    """
    _ = package  # reserved for multi-package later
    used_network = False
    source = "offline_default"
    err: str | None = None
    version: str | None = None

    active: UpstreamFetcher | None = fetcher
    if active is None and allow_network:
        active = default_pypi_fetcher
        used_network = True
        source = "pypi_json"
    elif active is not None:
        source = "injected_fetcher"
        # Injected fetchers may or may not hit network; we do not force network.

    if active is None:
        return {
            "ok": True,
            "version": None,
            "source": source,
            "allow_network": allow_network,
            "used_network": False,
            "error": None,
            "note": "No resolve (offline default). Pass fetcher= or allow_network=True.",
        }

    try:
        payload = active()
        version = _extract_version_from_payload(payload)
        if version is None:
            err = "Fetcher returned no parseable version"
            return {
                "ok": False,
                "version": None,
                "source": source,
                "allow_network": allow_network,
                "used_network": used_network,
                "error": err,
                "note": "Upstream resolve failed to parse a semver.",
            }
        return {
            "ok": True,
            "version": version,
            "source": source,
            "allow_network": allow_network,
            "used_network": used_network,
            "error": None,
            "note": f"Resolved upstream plate-core=={version} via {source}.",
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "ok": False,
            "version": None,
            "source": source,
            "allow_network": allow_network,
            "used_network": used_network,
            "error": str(exc),
            "note": "Upstream resolve failed; plan falls back to installed version.",
        }
    except Exception as exc:  # noqa: BLE001 — surface any fetcher failure cleanly
        return {
            "ok": False,
            "version": None,
            "source": source,
            "allow_network": allow_network,
            "used_network": used_network,
            "error": str(exc),
            "note": "Upstream resolve failed; plan falls back to installed version.",
        }


def plan_self_migrate(
    repo_root: str | Path | None = None,
    *,
    target_version: str | None = None,
    include_payload: bool = True,
    resolve_upstream: bool = False,
    allow_network: bool = False,
    upstream_fetcher: UpstreamFetcher | None = None,
) -> dict[str, Any]:
    """Build a dry-run self-migrate plan for the local checkout (#939 / #945).

    When ``target_version`` is omitted, uses installed plate-core ``__version__``
    as the upgrade target (no network). Pin files are compared to that target.

    When ``resolve_upstream`` is True, attempts :func:`resolve_upstream_version`
    (offline unless ``allow_network`` or ``upstream_fetcher``). On success the
    resolved version becomes the target (unless ``target_version`` was explicit).
    """
    root = Path(repo_root or ".").resolve()
    installed = _parse_semver(_INSTALLED_VERSION) or str(_INSTALLED_VERSION)
    pin = _detect_pin(root)
    pin_ver = pin.get("version")

    upstream_meta: dict[str, Any] | None = None
    resolved_target: str | None = None
    if resolve_upstream or upstream_fetcher is not None:
        upstream_meta = resolve_upstream_version(
            allow_network=allow_network,
            fetcher=upstream_fetcher,
        )
        if upstream_meta.get("ok") and upstream_meta.get("version"):
            resolved_target = str(upstream_meta["version"])

    if target_version:
        target = _parse_semver(target_version) or installed
    elif resolved_target:
        target = resolved_target
    else:
        target = installed
    if target is None:
        target = installed

    pin_vs_target = _compare(pin_ver, target)
    installed_vs_target = _compare(installed, target)
    pin_vs_installed = _compare(pin_ver, installed)

    # Drift = checkout still needs work to reach *target*:
    # - pin behind/ahead of target → align pin files
    # - installed behind target → upgrade runtime
    # Do NOT treat "installed ahead of pin" alone as drift when pin already
    # equals the target. That pattern is normal in the plate-core monorepo
    # after a packaging cut (tests pin an older explicit target while
    # PYTHONPATH loads the cut version) and is not pin/payload misalignment.
    drift = (
        pin_vs_target in ("behind", "ahead")
        or installed_vs_target == "behind"
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
            "description": (
                "gh plate self-migrate --verify --json "
                "(offline drift + adoption + .plate; then gh plate health if remote)"
            ),
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
    elif pin_vs_target == "behind" or installed_vs_target == "behind":
        next_cmd = f"pip install 'plate-core=={target}'"

    used_net = bool(upstream_meta and upstream_meta.get("used_network"))
    note = (
        "Plan only — no pip install or file writes. "
        "Human/agent executes steps after review (#649)."
    )
    if used_net:
        note = (
            "Plan only — no pip install or file writes. "
            "Upstream version resolved via network (allow_network); "
            "still no auto-apply (#945/#649)."
        )
    elif resolve_upstream or upstream_fetcher is not None:
        note = (
            "Plan only — no pip install or file writes. "
            "Upstream resolve attempted (see upstream field); default offline (#945)."
        )

    return {
        "ok": True,
        "mode": "dry_run_plan",
        "repo_root": str(root),
        "installed_version": installed,
        "pin": pin,
        "target_version": target,
        "upstream": upstream_meta,
        "resolve_upstream": bool(resolve_upstream or upstream_fetcher is not None),
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
        "note": note,
        "related_issues": ["#939", "#945", "#649", "#633", "#615", "#654"],
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


# Pin/source files that may be updated in a low-risk self-migrate PR.
_LOW_RISK_PIN_PATHS = frozenset(
    {
        "VERSION",
        "PLATE_CORE_VERSION",
        "gh-plate/VERSION",
        "requirements.txt",
        "pyproject.toml",
    }
)


def plan_self_migrate_pr(
    repo_root: str | Path | None = None,
    *,
    target_version: str | None = None,
    include_payload: bool = True,
    resolve_upstream: bool = False,
    allow_network: bool = False,
    upstream_fetcher: UpstreamFetcher | None = None,
    base: str = "release",
    closes: str | None = None,
    migrate_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dry-run migration PR plan from self-migrate status (#947 / #649).

    Pure helper: no git, no network (unless migrate_plan resolve is requested).
    Default base is legacy ``release``. Does not open a PR.
    """
    root = Path(repo_root or ".").resolve()
    plan = migrate_plan or plan_self_migrate(
        root,
        target_version=target_version,
        include_payload=include_payload,
        resolve_upstream=resolve_upstream,
        allow_network=allow_network,
        upstream_fetcher=upstream_fetcher,
    )
    if not plan.get("ok"):
        return {
            "ok": False,
            "error": "migrate_plan_failed",
            "migrate_plan": plan,
            "auto_apply": False,
        }

    target = str(plan.get("target_version") or "unknown")
    pin = plan.get("pin") or {}
    pin_source = pin.get("source")
    pin_path = None
    if pin.get("pins"):
        pin_path = pin["pins"][0].get("path")
    elif pin_source:
        # map source label to relative path when possible
        for p in pin.get("pins") or []:
            if p.get("source") == pin_source:
                pin_path = p.get("path")
                break

    file_intents: list[dict[str, Any]] = []
    if pin_source and plan.get("comparisons", {}).get("pin_vs_target") in (
        "behind",
        "ahead",
    ):
        rel = None
        if pin_path:
            try:
                rel = str(Path(pin_path).resolve().relative_to(root))
            except ValueError:
                rel = Path(pin_path).name
        else:
            rel = {
                "VERSION": "VERSION",
                "PLATE_CORE_VERSION": "PLATE_CORE_VERSION",
                "gh-plate/VERSION": "gh-plate/VERSION",
                "pyproject.toml": "pyproject.toml",
                "requirements.txt": "requirements.txt",
            }.get(str(pin_source), str(pin_source))
        file_intents.append(
            {
                "path": rel,
                "action": "align_pin",
                "from_version": pin.get("version"),
                "to_version": target,
                "low_risk": rel in _LOW_RISK_PIN_PATHS
                or Path(rel).name in ("VERSION", "PLATE_CORE_VERSION"),
            }
        )

    # Marker-bearing process files are medium when present; list as review-only intents
    for p in plan.get("refresh_paths_present") or []:
        if p.get("has_plates_core_markers") and p.get("path"):
            file_intents.append(
                {
                    "path": p["path"],
                    "action": "marker_review",
                    "low_risk": False,
                    "note": "Use --merge-markers with explicit --apply-markers after review",
                }
            )

    if not file_intents and not plan.get("drift"):
        return {
            "ok": True,
            "mode": "pr_plan",
            "eligible": False,
            "reason": "no_drift",
            "migrate_plan": plan,
            "base": base,
            "file_intents": [],
            "auto_apply": False,
            "note": "No pin/payload drift; migration PR not needed.",
            "related_issues": ["#947", "#649", "#945", "#943", "#939"],
        }

    if not file_intents and plan.get("drift"):
        # Drift from installed vs target without pin file: still plan runtime upgrade PR body
        file_intents.append(
            {
                "path": "PLATE_CORE_VERSION",
                "action": "align_pin_or_document",
                "from_version": plan.get("installed_version"),
                "to_version": target,
                "low_risk": True,
                "note": "Pin file may be absent; document upgrade in PR body",
            }
        )

    # Eligibility is pin-alignment only; marker_review is advisory (not auto-applied).
    pin_intents = [
        i
        for i in file_intents
        if i.get("action") in ("align_pin", "align_pin_or_document")
    ]
    marker_intents = [i for i in file_intents if i.get("action") == "marker_review"]
    pin_only_low = bool(pin_intents) and all(i.get("low_risk") for i in pin_intents)
    high_risk = not pin_only_low
    risk = "low" if pin_only_low else "medium"
    if marker_intents and not pin_only_low:
        risk = "medium"
        high_risk = True

    slug_ver = target.replace(".", "-")
    branch = f"chore/self-migrate-{slug_ver}"
    title = f"Self-migrate plate-core pin toward {target}"
    closes_line = f"\n\nCloses {closes}" if closes else ""
    body = (
        f"## Summary\n"
        f"- Self-migrate plan for plate-core target **{target}**\n"
        f"- Installed: {plan.get('installed_version')}; "
        f"pin: {pin.get('version')} ({pin.get('source')})\n"
        f"- Drift: {plan.get('drift')}; plan risk: {plan.get('risk')}\n"
        f"\n## File intents\n"
        + "\n".join(
            f"- `{i.get('path')}`: {i.get('action')} "
            f"({i.get('from_version')} → {i.get('to_version')})"
            if i.get("to_version")
            else f"- `{i.get('path')}`: {i.get('action')}"
            for i in file_intents
        )
        + "\n\n## Safety\n"
        "- Generated by `gh plate self-migrate --pr-plan` (#947)\n"
        "- Dry-run by default; apply requires explicit `--apply-pr` and low risk\n"
        "- Marker sections are advisory only — use --merge-markers separately\n"
        "- Does not auto-merge; no secrets\n"
        f"{closes_line}"
    ).strip() + "\n"

    # Commit paths: only pin alignments for low-risk auto PR
    paths = [str(i["path"]) for i in pin_intents if i.get("path")] or [
        str(i["path"]) for i in file_intents if i.get("path")
    ]
    labels = ["Feature", "Migration", "area:agent", f"risk:{risk}"]
    if high_risk:
        labels.append("need:human-review")

    git_steps = [
        f"git fetch origin {base}",
        f"git checkout -b {branch} origin/{base}",
        "apply pin intents: " + ", ".join(paths),
        "git add -- " + " ".join(paths),
        f'git commit -m "Self-migrate plate-core pin toward {target}"',
        f"git push -u origin {branch}",
    ]
    gh_argv = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
        "--label",
        ",".join(labels),
    ]

    eligible = bool(plan.get("drift")) and pin_only_low and risk == "low"
    return {
        "ok": True,
        "mode": "pr_plan",
        "eligible": eligible,
        "reason": (
            None
            if eligible
            else (
                "no_drift"
                if not plan.get("drift")
                else "not_low_risk_pin_only"
            )
        ),
        "migrate_plan": {
            "target_version": plan.get("target_version"),
            "installed_version": plan.get("installed_version"),
            "pin": plan.get("pin"),
            "drift": plan.get("drift"),
            "risk": plan.get("risk"),
            "comparisons": plan.get("comparisons"),
        },
        "base": base,
        "branch": branch,
        "title": title,
        "body": body,
        "labels": labels,
        "paths": paths,
        "file_intents": file_intents,
        "risk": risk,
        "high_risk": high_risk,
        "need_human_review": high_risk,
        "git_steps": git_steps,
        "gh_argv": gh_argv,
        "auto_apply": False,
        "auto_push": False,
        "note": (
            "PR plan only — no git push or gh pr create. "
            "Use apply_self_migrate_pr(dry_run=False) only when eligible and low risk (#947)."
        ),
        "related_issues": ["#947", "#649", "#945", "#943", "#939", "#654"],
        "next_command": "gh plate self-migrate --pr-plan --json",
    }


def apply_self_migrate_pr(
    plan: dict[str, Any] | None,
    *,
    dry_run: bool = True,
    allow_high_risk: bool = False,
    runner: Any | None = None,
) -> dict[str, Any]:
    """Apply or dry-run a self-migrate PR plan (#947).

    - dry_run=True (default): returns would_execute; no git/network.
    - dry_run=False: requires eligible low-risk plan (or allow_high_risk) and
      an injectable ``runner(plan)``; never auto-pushes without runner.
    """
    if not plan or not plan.get("ok"):
        return {
            "ok": False,
            "applied": False,
            "dry_run": dry_run,
            "error": (plan or {}).get("error") or "invalid_plan",
        }

    high_risk = bool(plan.get("high_risk") or plan.get("need_human_review"))
    steps = list(plan.get("git_steps") or []) + [
        " ".join(str(x) for x in (plan.get("gh_argv") or [])[:8]) + " ..."
    ]

    if dry_run:
        return {
            "ok": True,
            "applied": False,
            "dry_run": True,
            "would_execute": steps,
            "eligible": plan.get("eligible"),
            "high_risk": high_risk,
            "branch": plan.get("branch"),
            "base": plan.get("base"),
            "title": plan.get("title"),
            "note": "Dry-run only; no git push or gh pr create executed (#947).",
        }

    if high_risk and not allow_high_risk:
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": "high_risk_blocked",
            "high_risk": True,
            "note": "High/medium risk migration PR requires allow_high_risk=True and human review.",
        }

    if not plan.get("eligible") and not allow_high_risk:
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": "not_eligible",
            "eligible": False,
            "note": plan.get("reason") or "Plan not eligible for auto PR apply.",
        }

    if runner is None:
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": "runner_required",
            "would_execute": steps,
            "note": "Live apply needs injectable runner(plan); engine never pushes alone.",
        }

    try:
        result = runner(plan)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "applied": False,
            "dry_run": False,
            "error": str(exc),
            "note": "Runner failed during self-migrate PR apply.",
        }

    return {
        "ok": True,
        "applied": True,
        "dry_run": False,
        "high_risk": high_risk,
        "branch": plan.get("branch"),
        "base": plan.get("base"),
        "title": plan.get("title"),
        "runner_result": result,
        "note": "Runner completed; verify PR on GitHub before merge (#947).",
    }


def verify_self_migrate(
    repo_root: str | Path | None = None,
    *,
    target_version: str | None = None,
    include_payload: bool = True,
    resolve_upstream: bool = False,
    allow_network: bool = False,
    upstream_fetcher: UpstreamFetcher | None = None,
) -> dict[str, Any]:
    """Offline post-migrate verification: drift + adoption + .plate (#965 / #649).

    No network by default, no file writes, no pip install. Complements remote
    ``gh plate health`` which still needs GitHub when operators want full status.
    """
    root = Path(repo_root or ".").resolve()
    plan = plan_self_migrate(
        root,
        target_version=target_version,
        include_payload=include_payload,
        resolve_upstream=resolve_upstream,
        allow_network=allow_network,
        upstream_fetcher=upstream_fetcher,
    )

    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    drift = bool(plan.get("drift"))
    checks.append(
        {
            "id": "no_drift",
            "ok": not drift,
            "detail": {
                "drift": drift,
                "target_version": plan.get("target_version"),
                "comparisons": plan.get("comparisons"),
                "pin": plan.get("pin"),
            },
        }
    )
    if drift:
        failures.append("pin_or_payload_drift")

    adoption: dict[str, Any] = {}
    try:
        from .adoption import assess_adoption_readiness

        adoption = assess_adoption_readiness(root, include_optional=False)
        core_ready = bool(adoption.get("core_ready"))
        checks.append(
            {
                "id": "adoption_core_ready",
                "ok": core_ready,
                "detail": {
                    "core_ready": core_ready,
                    "first_qa_seeded": (adoption.get("first_qa") or {}).get("seeded"),
                    "next_command": adoption.get("next_command"),
                    "minutes_remaining": adoption.get("minutes_remaining"),
                },
            }
        )
        if not core_ready:
            failures.append("adoption_not_core_ready")
    except Exception as exc:  # noqa: BLE001
        checks.append(
            {
                "id": "adoption_core_ready",
                "ok": False,
                "detail": {"error": str(exc)},
            }
        )
        failures.append("adoption_check_error")
        adoption = {"error": str(exc)}

    plate_cfg: dict[str, Any] = {}
    plate_path = root / ".plate"
    if plate_path.is_file():
        try:
            from .plate_config import get_plate_config_report

            cfg = get_plate_config_report(root)
            plate_cfg = cfg.to_dict() if hasattr(cfg, "to_dict") else dict(cfg)  # type: ignore[arg-type]
            valid = bool(plate_cfg.get("valid"))
            checks.append(
                {
                    "id": "plate_config_valid",
                    "ok": valid,
                    "detail": {
                        "present": plate_cfg.get("present"),
                        "valid": valid,
                        "source": plate_cfg.get("source"),
                        "file_version": plate_cfg.get("file_version"),
                    },
                }
            )
            if not valid:
                failures.append("plate_config_invalid")
        except Exception as exc:  # noqa: BLE001
            checks.append(
                {
                    "id": "plate_config_valid",
                    "ok": False,
                    "detail": {"error": str(exc)},
                }
            )
            failures.append("plate_config_error")
            plate_cfg = {"error": str(exc)}
    else:
        checks.append(
            {
                "id": "plate_config_valid",
                "ok": True,
                "detail": {
                    "present": False,
                    "valid": None,
                    "note": "No .plate file; skipped (optional for bare checkouts).",
                },
            }
        )

    ready = len(failures) == 0
    next_cmd = "gh plate self-migrate --verify --json"
    if drift:
        next_cmd = plan.get("next_command") or "gh plate self-migrate --plan --json"
    elif not (adoption.get("core_ready") if adoption else True):
        next_cmd = adoption.get("next_command") or "gh plate adopt --json"

    note = (
        "Post-migrate verify offline (#965). "
        "ready=true means no pin/payload drift, adoption core_ready, and valid .plate when present. "
        "Run gh plate health for remote GitHub signals."
    )
    if not ready:
        note = (
            "Post-migrate verify found residual work (#965): "
            + ", ".join(failures)
            + ". Address then re-run --verify."
        )

    return {
        "ok": True,
        "mode": "verify",
        "repo_root": str(root),
        "ready": ready,
        "failures": failures,
        "checks": checks,
        "migrate": {
            "drift": drift,
            "target_version": plan.get("target_version"),
            "risk": plan.get("risk"),
            "comparisons": plan.get("comparisons"),
            "pin": plan.get("pin"),
            "installed_version": plan.get("installed_version"),
        },
        "adoption": {
            "core_ready": adoption.get("core_ready"),
            "first_qa_seeded": (adoption.get("first_qa") or {}).get("seeded")
            if isinstance(adoption.get("first_qa"), dict)
            else adoption.get("first_qa_seeded"),
            "next_command": adoption.get("next_command"),
            "error": adoption.get("error"),
        },
        "plate_config": {
            "present": plate_cfg.get("present") if plate_cfg else False,
            "valid": plate_cfg.get("valid"),
            "source": plate_cfg.get("source"),
            "file_version": plate_cfg.get("file_version"),
            "error": plate_cfg.get("error"),
        },
        "next_command": next_cmd,
        "auto_apply": False,
        "note": note,
        "related_issues": ["#965", "#649", "#939", "#947", "#633", "#654"],
        "ask_user_question": {
            "question": (
                f"Self-migrate verify ready={ready} (failures={failures or 'none'}). Next?"
            ),
            "options": [
                {
                    "label": "Re-plan migrate",
                    "description": "gh plate self-migrate --plan --json",
                },
                {
                    "label": "Adoption status",
                    "description": "gh plate adopt --json",
                },
                {
                    "label": "Remote health",
                    "description": "gh plate health",
                },
                {"label": "Done", "description": "No further migrate work"},
            ],
        },
    }
