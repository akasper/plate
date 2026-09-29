"""First-class template payload import for adoption (#616 / Epic #615).

Plan and apply the canonical PLATE template payload into a target checkout
(local filesystem). Strategies:

- ``safe`` (default): create missing files only; skip existing paths.
- ``conservative``: create missing only; report conflicts when content differs;
  never overwrite.
- ``force``: write all payload files (overwrite existing).

Dry-run reports would-create / would-skip / would-conflict without side effects.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .template_payload import (
    classify_template_file,
    load_template_payload_manifest,
    resolve_conflict_plan,
    resolve_template_source,
    should_include_template_file,
)

Strategy = Literal["safe", "conservative", "force"]
VALID_STRATEGIES: tuple[str, ...] = ("safe", "conservative", "force")

# Minimal CURRENT.md for adoption/import when absent (#618).
# Not in payload include_globs (repo-specific); seeded by importer.
# Avoids validate_plate_repo placeholder phrase about generic template CI.
MINIMAL_CURRENT_MD = """# CURRENT — implemented state (starter)

> **Preferred durable evidence:** `.agentic/releases/` fragments and versioned
> release notes. This file is a lightweight index for older tooling
> (`scripts/validate_plate_repo.sh`, feature detection) and adoption.

## Adoption note

This repository adopted PLATE via `gh plate import-payload` / bootstrap.
Product claims live in the project's existing README, CHANGELOG, roadmap, or
docs — do not treat this file as the product source of truth.

## Implemented capability index

| Capability | Status | Evidence |
|---|---|---|
| PLATE process scaffolding present | Started | `.plate` (after bootstrap), `.github/` PLATE workflows, `AGENTS.md` if installed |
| Release fragments layout | Planned / partial | `.agentic/releases/unreleased/` |
| Demo / E2E evidence | Optional | Playwright / media paths when configured |

## CI / toolchain

CI is project-owned. After adoption, keep product CI (e.g. `.github/workflows/ci.yml`)
and enable PLATE process workflows (e.g. `plate-ci.yml` when installed via path_rules).
Update this table when real test commands are documented for agents.

## Next steps

1. Run `gh plate health` and close remaining gaps.
2. Author fragments under `.agentic/releases/unreleased/` for Feature work.
3. Replace placeholder rows above with real capability rows + links to PRs/tests.
"""


@dataclass
class PayloadFileDecision:
    path: str
    action: str  # create | skip | conflict | overwrite | create_as
    classification: str
    detail: str = ""
    target_path: str = ""  # write destination (may differ for install_as)
    rule: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImportPayloadReport:
    apply_mode: bool
    strategy: str
    target_dir: str
    template_source: str
    template_root: str
    files: list[PayloadFileDecision] = field(default_factory=list)
    would_create: list[str] = field(default_factory=list)
    would_skip: list[str] = field(default_factory=list)
    would_conflict: list[str] = field(default_factory=list)
    would_overwrite: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    next_command: str = ""
    namespace_scripts: bool = False
    namespace_docs: bool = False
    platform: str = "posix"
    omitted_for_platform: list[str] = field(default_factory=list)
    ok: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "apply_mode": self.apply_mode,
            "strategy": self.strategy,
            "target_dir": self.target_dir,
            "template_source": self.template_source,
            "template_root": self.template_root,
            "namespace_scripts": self.namespace_scripts,
            "namespace_docs": self.namespace_docs,
            "platform": self.platform,
            "omitted_for_platform": list(self.omitted_for_platform),
            "counts": {
                "payload_files": len(self.files),
                "would_create": len(self.would_create),
                "would_skip": len(self.would_skip),
                "would_conflict": len(self.would_conflict),
                "would_overwrite": len(self.would_overwrite),
                "created": len(self.created),
                "skipped": len(self.skipped),
                "conflicts": len(self.conflicts),
                "overwritten": len(self.overwritten),
                "omitted_for_platform": len(self.omitted_for_platform),
            },
            "would_create": list(self.would_create),
            "would_skip": list(self.would_skip),
            "would_conflict": list(self.would_conflict),
            "would_overwrite": list(self.would_overwrite),
            "created": list(self.created),
            "skipped": list(self.skipped),
            "conflicts": list(self.conflicts),
            "overwritten": list(self.overwritten),
            "files": [f.to_dict() for f in self.files],
            "next_steps": list(self.next_steps),
            "next_command": self.next_command or _next_command(self),
        }


def list_payload_relative_paths(template_root: Path | None = None) -> list[str]:
    """Return manifest-filtered relative paths under the template payload root."""
    root = Path(template_root) if template_root is not None else resolve_template_source()[0]
    manifest = load_template_payload_manifest()
    rel_paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if should_include_template_file(rel, manifest):
            rel_paths.append(rel)
    return rel_paths


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _should_rewrite_docs_refs(rel: str) -> bool:
    """True when file should have docs/ refs rewritten during namespace (#1015)."""
    # AGENTS.md at root references docs/ paths extensively
    if rel == "AGENTS.md":
        return True
    # Workflows may reference docs/ paths
    if rel.startswith(".github/workflows/"):
        return True
    # Issue templates may reference docs/
    if rel.startswith(".github/ISSUE_TEMPLATE/"):
        return True
    # SPEC.md and other root markdown
    if rel in ("SPEC.md", "CONTRIBUTING.md", "README.md", "CURRENT.md"):
        return True
    # Markdown files under .agentic/ that might reference docs/
    if rel.startswith(".agentic/") and rel.endswith((".md", ".yml", ".yaml")):
        return True
    # Agent files and copilot instructions
    if rel.startswith(".github/agents/") or rel == ".github/copilot-instructions.md":
        return True
    # Markdown files in scripts/ (like README.md)
    if rel.startswith("scripts/") and rel.endswith(".md"):
        return True
    # Payload docs are installed under docs/plate/ and must rewrite their own
    # docs/wiki, docs/research, and sibling links (#1015 / #1016).
    if rel.startswith("docs/") and rel.endswith((".md", ".yml", ".yaml", ".txt")):
        return True
    return False


def _decide_file(
    *,
    rel: str,
    source: Path,
    dest: Path,
    strategy: Strategy,
    classification: str,
    manifest: Any = None,
) -> PayloadFileDecision:
    from .template_payload import load_template_payload_manifest

    mf = manifest if manifest is not None else load_template_payload_manifest()
    identical = False
    if dest.exists() and dest.is_file() and source.is_file():
        try:
            identical = _file_sha256(dest) == _file_sha256(source)
        except OSError:
            identical = False

    plan = resolve_conflict_plan(
        rel,
        dest_exists=dest.exists(),
        identical=identical,
        strategy=strategy,
        manifest=mf,
    )
    target = str(plan.get("target_path") or rel)
    return PayloadFileDecision(
        path=rel,
        action=str(plan.get("action") or "skip"),
        classification=classification,
        detail=str(plan.get("detail") or ""),
        target_path=target,
        rule=plan.get("rule") if isinstance(plan.get("rule"), dict) else None,
    )


def _strategy_flag(strategy: str) -> str:
    strat = str(strategy or "safe").lower()
    if strat not in VALID_STRATEGIES:
        strat = "safe"
    return f"--strategy {strat}"


def _next_command(report: ImportPayloadReport | dict[str, Any]) -> str:
    """Single actionable next CLI for agents/adopters (parity with adopt/self-migrate).

    Priority:
    1. Invalid/error → re-run dry-run with a valid strategy
    2. Dry-run with hard conflicts → escape-hatch plan for human review
    3. Dry-run with pending writes → ``--apply`` same strategy
    4. Apply wrote files → bootstrap GitHub-side adoption
    5. Apply left conflicts → escape hatch (do not force)
    6. Nothing pending → readiness/health
    """
    if isinstance(report, dict):
        ok = report.get("ok", True)
        error = report.get("error")
        apply_mode = bool(report.get("apply_mode"))
        strategy = str(report.get("strategy") or "safe")
        would_create = list(report.get("would_create") or [])
        would_overwrite = list(report.get("would_overwrite") or [])
        would_conflict = list(report.get("would_conflict") or [])
        created = list(report.get("created") or [])
        overwritten = list(report.get("overwritten") or [])
        conflicts = list(report.get("conflicts") or [])
    else:
        ok = report.ok
        error = report.error
        apply_mode = report.apply_mode
        strategy = report.strategy
        would_create = report.would_create
        would_overwrite = report.would_overwrite
        would_conflict = report.would_conflict
        created = report.created
        overwritten = report.overwritten
        conflicts = report.conflicts

    strat = _strategy_flag(strategy)
    if not ok:
        if error and "Invalid strategy" in str(error):
            return "gh plate import-payload --dry-run --strategy conservative --json"
        return f"gh plate import-payload --dry-run {strat} --json"

    if not apply_mode:
        if would_conflict:
            return (
                f"gh plate import-payload --dry-run {strat} "
                "--escape-hatch .agentic/import-escape-hatch --json"
            )
        if would_create or would_overwrite:
            return f"gh plate import-payload --apply {strat}"
        return "gh plate adopt --json"

    if conflicts and not (created or overwritten):
        return (
            f"gh plate import-payload --dry-run {strat} "
            "--escape-hatch .agentic/import-escape-hatch --json"
        )
    if created or overwritten:
        return "gh plate bootstrap --repo OWNER/REPO --adopt --apply"
    if conflicts:
        return (
            f"gh plate import-payload --dry-run {strat} "
            "--escape-hatch .agentic/import-escape-hatch --json"
        )
    return "gh plate adopt --json"


def _next_steps(report: ImportPayloadReport) -> list[str]:
    next_cmd = _next_command(report)
    steps = [
        f"Next command: `{next_cmd}`",
        "Review would_create / would_conflict lists before --apply on real repos.",
        "After local apply: commit scaffolding, run `gh plate bootstrap --apply` (or `--adopt`) for labels/wiki/.plate GitHub-side setup.",
        "Run `gh plate health` and open the first Curiosity Q&A session when healthy.",
        "Prefer `.agentic/releases/unreleased/` fragments for durable implemented-state; keep CURRENT.md as a short index (#618).",
    ]
    if report.would_conflict or report.conflicts:
        steps.insert(
            1,
            "Hard conflicts: run with --escape-hatch DIR (or plate_import_payload escape_hatch_dir) "
            "to write plan.json + PLAN.md + DRAFT_PR_BODY.md for human review (#622); "
            "do not use --strategy force without explicit human approval on high-value paths.",
        )
        steps.insert(
            2,
            "Resolve would_conflict paths manually or re-run with --strategy force only if intentional overwrite is desired.",
        )
    if report.apply_mode and (report.created or report.overwritten):
        steps.insert(1, "git status + review diffs for newly written payload files.")
    if any(x == "CURRENT.md" or x.endswith("CURRENT.md") for x in report.would_create):
        steps.insert(
            1,
            "Fill CURRENT.md capability rows (or deprecate to fragments) once real features land.",
        )
    return steps


def resolve_import_platform(explicit: str | None, target: Path) -> str:
    """CLI flag wins, then the target ``.plate`` value, then ``posix``.

    Does not look at the operator machine. An unknown stored or explicit value
    raises ``PlateConfigError``.
    """
    from .plate_config import ALLOWED_PLATFORMS, PLATFORM_POSIX, PlateConfigError

    if explicit is not None:
        if not isinstance(explicit, str):
            allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
            raise PlateConfigError(f"invalid platform: {explicit!r} (allowed: {allowed})")
        value = explicit.strip()
        if value:
            if value not in ALLOWED_PLATFORMS:
                allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
                raise PlateConfigError(f"invalid platform: {value!r} (allowed: {allowed})")
            return value

    plate_path = target / ".plate"
    if not plate_path.is_file():
        return PLATFORM_POSIX
    try:
        data = json.loads(plate_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlateConfigError(f"invalid JSON in .plate: {exc}") from exc
    if not isinstance(data, dict):
        raise PlateConfigError(".plate must contain a top-level object")
    stored = data.get("platform")
    if stored is None or stored == "":
        return PLATFORM_POSIX
    if not isinstance(stored, str) or stored not in ALLOWED_PLATFORMS:
        allowed = ", ".join(sorted(ALLOWED_PLATFORMS))
        raise PlateConfigError(f"invalid platform: {stored!r} (allowed: {allowed})")
    return stored


def _render_payload_bytes(
    source: Path,
    rel: str,
    *,
    platform: str,
    namespaced_scripts: bool,
    namespaced_docs: bool,
) -> bytes:
    data = source.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    from .payload_surface import prepare_copied_text, rewrite_docs_refs

    text = prepare_copied_text(rel, text, platform, namespaced=namespaced_scripts)
    if namespaced_docs and _should_rewrite_docs_refs(rel):
        text = rewrite_docs_refs(text)
    return text.encode("utf-8")


def plan_import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    apply: bool = False,
    namespace_scripts: bool | None = None,
    namespace_docs: bool | None = None,
    platform: str | None = None,
) -> ImportPayloadReport:
    """Plan (and optionally apply) template payload import into a local target dir.

    ``namespace_scripts``: when True, install PLATE scripts under ``scripts/plate/``
    and rewrite workflow script refs (#621). None = auto-detect if target has a
    non-empty product ``scripts/`` tree.
    
    ``namespace_docs``: when True, install PLATE docs under ``docs/plate/``
    and rewrite doc refs (#1015). None = auto-detect if target has a
    non-empty product ``docs/`` tree.
    """
    from .payload_surface import (
        filter_plate_scripts,
        namespace_docs_path,
        namespace_script_path,
        should_namespace_docs,
        should_namespace_scripts,
    )
    from .plate_config import PlateConfigError

    strat = str(strategy or "safe").lower()
    if strat not in VALID_STRATEGIES:
        return ImportPayloadReport(
            apply_mode=bool(apply),
            strategy=strat,
            target_dir=str(Path(target_dir).resolve()),
            template_source="",
            template_root="",
            ok=False,
            error=f"Invalid strategy {strategy!r}; expected one of {VALID_STRATEGIES}",
        )

    target = Path(target_dir).resolve()
    try:
        template_root, source_kind = resolve_template_source(template_repo)
    except Exception as exc:
        return ImportPayloadReport(
            apply_mode=bool(apply),
            strategy=strat,
            target_dir=str(target),
            template_source="",
            template_root="",
            ok=False,
            error=str(exc),
        )

    if not target.exists():
        if apply:
            target.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            return ImportPayloadReport(
                apply_mode=bool(apply),
                strategy=strat,
                target_dir=str(target),
                template_source=source_kind,
                template_root=str(template_root),
                ok=False,
                error=f"Target directory does not exist: {target}",
            )

    ns = (
        bool(namespace_scripts)
        if namespace_scripts is not None
        else should_namespace_scripts(target)
    )
    
    nd = (
        bool(namespace_docs)
        if namespace_docs is not None
        else should_namespace_docs(target)
    )

    explicit_platform = platform is not None and str(platform).strip() != ""
    try:
        resolved_platform = resolve_import_platform(platform, target)
    except PlateConfigError as exc:
        return ImportPayloadReport(
            apply_mode=bool(apply),
            strategy=strat,
            target_dir=str(target),
            template_source=source_kind,
            template_root=str(template_root),
            ok=False,
            error=str(exc),
        )

    manifest = load_template_payload_manifest()
    rel_paths, omitted = filter_plate_scripts(
        list_payload_relative_paths(template_root),
        resolved_platform,
    )
    report = ImportPayloadReport(
        apply_mode=bool(apply),
        strategy=strat,
        target_dir=str(target),
        template_source=source_kind,
        template_root=str(template_root),
        namespace_scripts=ns,
        namespace_docs=nd,
        platform=resolved_platform,
        omitted_for_platform=omitted,
    )
    if explicit_platform and apply and (target / ".plate").is_file():
        try:
            _set_plate_platform(target / ".plate", resolved_platform)
        except PlateConfigError as exc:
            report.ok = False
            report.error = str(exc)
            return report

    for rel in rel_paths:
        source = template_root / rel
        # Prefer namespaced install path for plate scripts/docs when adopting (#621, #1015)
        preferred_rel = rel
        if ns and rel.startswith("scripts/"):
            preferred_rel = namespace_script_path(rel)
        elif nd and rel.startswith("docs/"):
            preferred_rel = namespace_docs_path(rel)
        
        dest = target / preferred_rel
        classification = classify_template_file(rel, manifest)
        decision = _decide_file(
            rel=rel,
            source=source,
            dest=dest,
            strategy=strat,  # type: ignore[arg-type]
            classification=classification,
            manifest=manifest,
        )
        # Override target_path for namespaced scripts/docs (path_rules install_as wins if set)
        if (ns and rel.startswith("scripts/")) or (nd and rel.startswith("docs/")):
            if decision.action in ("create", "create_as", "overwrite", "skip", "conflict"):
                if decision.action != "create_as" or not decision.target_path:
                    decision.target_path = preferred_rel
                if preferred_rel != rel and decision.action == "create":
                    issue_ref = "#621" if rel.startswith("scripts/") else "#1015"
                    decision.detail = (
                        f"{decision.detail}; namespaced to {preferred_rel} ({issue_ref})"
                        if decision.detail
                        else f"namespaced to {preferred_rel} ({issue_ref})"
                    )
        report.files.append(decision)
        write_rel = decision.target_path or preferred_rel
        write_dest = target / write_rel

        if decision.action in ("create", "create_as"):
            label = f"{rel} -> {write_rel}" if write_rel != rel else rel
            if decision.action == "create_as" and write_dest.exists():
                report.would_conflict.append(label)
                if apply:
                    report.conflicts.append(label)
                    decision.action = "conflict"
                decision.detail = f"{decision.detail}; install_as path also exists"
            else:
                report.would_create.append(label)
                if apply:
                    write_dest.parent.mkdir(parents=True, exist_ok=True)
                    data = _render_payload_bytes(
                        source,
                        rel,
                        platform=resolved_platform,
                        namespaced_scripts=ns,
                        namespaced_docs=nd,
                    )
                    write_dest.write_bytes(data)
                    report.created.append(label)
        elif decision.action == "overwrite":
            label = f"{rel} -> {write_rel}" if write_rel != rel else rel
            report.would_overwrite.append(label)
            if apply:
                write_dest.parent.mkdir(parents=True, exist_ok=True)
                data = _render_payload_bytes(
                    source,
                    rel,
                    platform=resolved_platform,
                    namespaced_scripts=ns,
                    namespaced_docs=nd,
                )
                write_dest.write_bytes(data)
                report.overwritten.append(label)
        elif decision.action == "conflict":
            report.would_conflict.append(rel)
            if apply:
                report.conflicts.append(rel)
        else:
            report.would_skip.append(rel if write_rel == rel else f"{rel} -> {write_rel}")
            if apply:
                report.skipped.append(rel)

    # #618: CURRENT.md is repo-specific (not in payload globs) but required by
    # validate_plate_repo + feature detection — seed when missing.
    _seed_current_md_if_missing(target, report, apply=bool(apply))
    # Adopter core_ready requires .agentic/releases[/unreleased] (#996 follow-on /
    # under-30m path). Template payload ships .agentic/*.yml only — seed layout.
    _seed_releases_layout_if_missing(target, report, apply=bool(apply))
    # Root .plate is not in template payload globs; seed DEFAULT_CONFIG JSON when
    # missing so local import can reach adoption core_ready without remote bootstrap.
    # Never overwrite an existing .plate (adopter customizations win).
    _seed_plate_config_if_missing(
        target,
        report,
        apply=bool(apply),
        platform=resolved_platform,
    )

    report.next_command = _next_command(report)
    report.next_steps = _next_steps(report)
    if ns:
        report.next_steps.insert(
            0,
            "PLATE scripts install under scripts/plate/; workflows rewritten to match (#621).",
        )
    if nd:
        report.next_steps.insert(
            0,
            "PLATE docs install under docs/plate/; references rewritten to match (#1015).",
        )
    if omitted:
        report.next_steps.insert(
            0,
            f"Omitted {len(omitted)} PLATE-owned script twin(s) for platform {resolved_platform}. "
            "Adopter-owned scripts are not removed.",
        )
    return report


def build_minimal_current_md(*, has_playwright: bool = False) -> str:
    """Return starter CURRENT.md body (#618)."""
    body = MINIMAL_CURRENT_MD
    if has_playwright:
        body = body.replace(
            "| Demo / E2E evidence | Optional | Playwright / media paths when configured |",
            "| Demo / E2E evidence | Detected | `playwright.config.ts` / `tests/e2e` present |",
        )
    return body


def _seed_current_md_if_missing(
    target: Path,
    report: ImportPayloadReport,
    *,
    apply: bool,
) -> None:
    """Append CURRENT.md create decision when absent; write on apply."""
    dest = target / "CURRENT.md"
    decision_base = {
        "path": "CURRENT.md",
        "classification": "adoption_seed",
        "target_path": "CURRENT.md",
        "rule": None,
    }
    if dest.exists():
        report.files.append(
            PayloadFileDecision(
                action="skip",
                detail="CURRENT.md already present",
                **decision_base,  # type: ignore[arg-type]
            )
        )
        report.would_skip.append("CURRENT.md")
        if apply:
            report.skipped.append("CURRENT.md")
        return

    has_pw = (target / "playwright.config.ts").is_file() or (
        target / "tests" / "e2e"
    ).is_dir()
    # Also detect if we just planned/created playwright from payload
    if not has_pw:
        for item in report.would_create + report.created:
            if "playwright.config.ts" in item or "tests/e2e" in item:
                has_pw = True
                break

    content = build_minimal_current_md(has_playwright=has_pw)
    report.files.append(
        PayloadFileDecision(
            action="create",
            detail="seed minimal CURRENT.md for validate + feature detection (#618)",
            **decision_base,  # type: ignore[arg-type]
        )
    )
    report.would_create.append("CURRENT.md")
    if apply:
        dest.write_text(content, encoding="utf-8")
        report.created.append("CURRENT.md")


# Minimal unreleased README so adoption readiness sees releases layout without
# shipping every monorepo fragment. Keep short; full contract is upstream docs.
MINIMAL_UNRELEASED_README = """# PLATE unreleased fragments

This directory holds release-note fragments not yet tied to a versioned release.

Author Feature/process changes as `<slug>.json` here (see PLATE fragment contract
in upstream `akasper/plate` / `docs` and `AGENTS.md`). At release cut, fragments
aggregate into `.agentic/releases/vX.Y.Z/`.

This starter file was seeded by `gh plate import-payload` so adoption readiness
(`core_ready`) can see a valid `.agentic/releases/unreleased/` layout.
"""


def _seed_releases_layout_if_missing(
    target: Path,
    report: ImportPayloadReport,
    *,
    apply: bool,
) -> None:
    """Ensure `.agentic/releases/unreleased/` exists for adoption core_ready.

    assess_adoption_readiness requires ``.agentic/releases`` plus ``unreleased``
    (or a ``v*`` dir). Template payload does not ship that empty tree, so pure
    import left adopters stuck on bootstrap for a directory mkdir (#996 path).
    """
    releases = target / ".agentic" / "releases"
    unreleased = releases / "unreleased"
    readme = unreleased / "README.md"
    rel = ".agentic/releases/unreleased/README.md"
    decision_base = {
        "path": rel,
        "classification": "adoption_seed",
        "target_path": rel,
        "rule": None,
    }

    layout_ok = releases.is_dir() and (
        unreleased.is_dir() or any(releases.glob("v*"))
    )
    if layout_ok and readme.is_file():
        report.files.append(
            PayloadFileDecision(
                action="skip",
                detail="releases/unreleased layout already present",
                **decision_base,  # type: ignore[arg-type]
            )
        )
        report.would_skip.append(rel)
        if apply:
            report.skipped.append(rel)
        return

    if layout_ok and not readme.is_file():
        # Dir exists (maybe empty) — still seed README for discoverability
        report.files.append(
            PayloadFileDecision(
                action="create",
                detail="seed unreleased README for fragment authoring",
                **decision_base,  # type: ignore[arg-type]
            )
        )
        report.would_create.append(rel)
        if apply:
            readme.write_text(MINIMAL_UNRELEASED_README, encoding="utf-8")
            report.created.append(rel)
        return

    report.files.append(
        PayloadFileDecision(
            action="create",
            detail=(
                "seed .agentic/releases/unreleased/ for adoption core_ready "
                "(template payload omits empty releases tree)"
            ),
            **decision_base,  # type: ignore[arg-type]
        )
    )
    report.would_create.append(rel)
    if apply:
        unreleased.mkdir(parents=True, exist_ok=True)
        readme.write_text(MINIMAL_UNRELEASED_README, encoding="utf-8")
        report.created.append(rel)


def _set_plate_platform(path: Path, platform: str) -> None:
    """Set ``platform`` on an existing ``.plate`` without touching other keys."""
    from .plate_config import PlateConfigError

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlateConfigError(f"invalid JSON in .plate: {exc}") from exc
    if not isinstance(data, dict):
        raise PlateConfigError(".plate must contain a top-level object")
    if data.get("platform") == platform:
        return
    data["platform"] = platform
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _seed_plate_config_if_missing(
    target: Path,
    report: ImportPayloadReport,
    *,
    apply: bool,
    platform: str | None = None,
) -> None:
    """Seed root ``.plate`` JSON from DEFAULT_CONFIG when absent (never overwrite).

    Same baseline bootstrap writes remotely (#259). Local import path needs this
    for ``assess_adoption_readiness`` plate_config check without GitHub API.
    File format is **JSON** (YAML ``version: 1`` is invalid and fails verify).
    """
    dest = target / ".plate"
    decision_base = {
        "path": ".plate",
        "classification": "adoption_seed",
        "target_path": ".plate",
        "rule": None,
    }
    if dest.exists():
        report.files.append(
            PayloadFileDecision(
                action="skip",
                detail=".plate already present (not overwritten)",
                **decision_base,  # type: ignore[arg-type]
            )
        )
        report.would_skip.append(".plate")
        if apply:
            report.skipped.append(".plate")
        return

    import copy

    from .plate_config import DEFAULT_CONFIG

    seeded = copy.deepcopy(DEFAULT_CONFIG)
    if platform:
        seeded["platform"] = platform
    payload = json.dumps(seeded, indent=2) + "\n"
    report.files.append(
        PayloadFileDecision(
            action="create",
            detail="seed DEFAULT_CONFIG .plate JSON for adoption core_ready (same as bootstrap)",
            **decision_base,  # type: ignore[arg-type]
        )
    )
    report.would_create.append(".plate")
    if apply:
        dest.write_text(payload, encoding="utf-8")
        report.created.append(".plate")


def copy_template_payload_local(
    dest_root: str | Path,
    *,
    source_root: str | Path | None = None,
    strategy: str = "safe",
    dry_run: bool = True,
    namespace_scripts: bool | None = None,
    namespace_docs: bool | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    """#620 local FS applier — same report as import_payload / plan_import_payload.

    ``source_root`` maps to ``template_repo`` (explicit template root). Default uses
    package payload. Prefer this name from bootstrap/agent code that already thinks
    in copy(source, dest) terms; CLI remains ``gh plate import-payload``.
    """
    return import_payload(
        dest_root,
        strategy=strategy,
        template_repo=str(source_root) if source_root is not None else None,
        dry_run=dry_run,
        apply=not dry_run,
        namespace_scripts=namespace_scripts,
        namespace_docs=namespace_docs,
        platform=platform,
    )


def format_import_payload_report(report: dict[str, Any] | ImportPayloadReport) -> str:
    """Human-readable summary for CLI."""
    data = report.to_dict() if isinstance(report, ImportPayloadReport) else report
    counts = data.get("counts") or {}
    mode = "APPLY" if data.get("apply_mode") else "DRY-RUN"
    lines = [
        f"## import-payload ({mode}) strategy={data.get('strategy')}",
        f"- Target: {data.get('target_dir')}",
        f"- Source: {data.get('template_source')} ({data.get('template_root')})",
        f"- Platform: {data.get('platform', 'posix')}",
        f"- Payload files: {counts.get('payload_files', 0)}",
        f"- Omitted for platform: {counts.get('omitted_for_platform', 0)}",
        f"- Would create: {counts.get('would_create', 0)} | skip: {counts.get('would_skip', 0)} "
        f"| conflict: {counts.get('would_conflict', 0)} | overwrite: {counts.get('would_overwrite', 0)}",
    ]
    if data.get("apply_mode"):
        lines.append(
            f"- Applied create: {counts.get('created', 0)} | skip: {counts.get('skipped', 0)} "
            f"| conflict: {counts.get('conflicts', 0)} | overwrite: {counts.get('overwritten', 0)}"
        )
    if data.get("error"):
        lines.append(f"- ERROR: {data.get('error')}")
    create_sample = (data.get("would_create") or [])[:8]
    if create_sample:
        lines.append("- Sample would_create:")
        for p in create_sample:
            lines.append(f"  - {p}")
    conflict_sample = (data.get("would_conflict") or data.get("conflicts") or [])[:8]
    if conflict_sample:
        lines.append("- Conflicts:")
        for p in conflict_sample:
            lines.append(f"  - {p}")
    next_cmd = data.get("next_command") or ""
    if next_cmd:
        lines.append(f"- Next command: `{next_cmd}`")
    steps = data.get("next_steps") or []
    if steps:
        lines.append("- Next steps:")
        for s in steps:
            lines.append(f"  - {s}")
    if data.get("escape_hatch"):
        eh = data["escape_hatch"]
        lines.append(f"- Escape hatch (#622): dir={eh.get('dir')}")
        for k in ("plan_json", "plan_md", "draft_pr_body"):
            if eh.get(k):
                lines.append(f"  - {k}: {eh.get(k)}")
    return "\n".join(lines) + "\n"


def render_import_plan_markdown(report: dict[str, Any] | ImportPayloadReport) -> str:
    """Rich plan markdown for agent/human review (#622)."""
    data = report.to_dict() if isinstance(report, ImportPayloadReport) else dict(report)
    counts = data.get("counts") or {}
    lines = [
        "# PLATE import-payload plan (#622 escape hatch)",
        "",
        f"- Strategy: `{data.get('strategy')}`",
        f"- Mode: `{'apply' if data.get('apply_mode') else 'dry-run'}`",
        f"- Target: `{data.get('target_dir')}`",
        f"- Source: `{data.get('template_source')}` (`{data.get('template_root')}`)",
        f"- Counts: create={counts.get('would_create', 0)} skip={counts.get('would_skip', 0)} "
        f"conflict={counts.get('would_conflict', 0)} overwrite={counts.get('would_overwrite', 0)}",
        "",
        "## Payload additions (would_create)",
    ]
    for p in data.get("would_create") or []:
        lines.append(f"- `{p}`")
    if not (data.get("would_create") or []):
        lines.append("- _(none)_")
    lines.extend(["", "## Preserved / skipped (would_skip)"])
    for p in (data.get("would_skip") or [])[:40]:
        lines.append(f"- `{p}`")
    if len(data.get("would_skip") or []) > 40:
        lines.append(f"- … +{len(data['would_skip']) - 40} more")
    if not (data.get("would_skip") or []):
        lines.append("- _(none)_")
    lines.extend(["", "## Conflicts (need human judgment)"])
    for p in data.get("would_conflict") or data.get("conflicts") or []:
        lines.append(f"- `{p}`")
    if not (data.get("would_conflict") or data.get("conflicts") or []):
        lines.append("- _(none)_")
    lines.extend(["", "## Would overwrite (force strategy only)"])
    for p in data.get("would_overwrite") or data.get("overwritten") or []:
        lines.append(f"- `{p}`")
    if not (data.get("would_overwrite") or data.get("overwritten") or []):
        lines.append("- _(none)_")
    lines.extend(["", "## Suggested renames / install_as"])
    renamed = [
        f
        for f in (data.get("files") or [])
        if isinstance(f, dict)
        and f.get("target_path")
        and f.get("target_path") != f.get("path")
    ]
    for f in renamed[:30]:
        lines.append(f"- `{f.get('path')}` → `{f.get('target_path')}` ({f.get('action')})")
    if not renamed:
        lines.append("- _(none detected in plan)_")
    lines.extend(["", "## Next steps"])
    for s in data.get("next_steps") or []:
        lines.append(f"- {s}")
    lines.extend(
        [
            "",
            "## Human approval gate",
            "- Do **not** use `force` overwrite on product-owned roots without explicit human approval.",
            "- Prefer draft PR / worktree review for irreducible conflicts (AGENTS.md human checkpoints).",
            "- SPEC.md / AGENTS.md / workflows / secrets remain high-risk paths.",
            "",
        ]
    )
    return "\n".join(lines)


def render_import_draft_pr_body(report: dict[str, Any] | ImportPayloadReport) -> str:
    """Draft PR body sections for human review of hard import merges (#622)."""
    data = report.to_dict() if isinstance(report, ImportPayloadReport) else dict(report)
    counts = data.get("counts") or {}
    conflicts = list(data.get("would_conflict") or data.get("conflicts") or [])
    creates = list(data.get("would_create") or data.get("created") or [])
    skips = list(data.get("would_skip") or data.get("skipped") or [])
    overwrites = list(data.get("would_overwrite") or data.get("overwritten") or [])

    def _bullets(items: list[str], *, limit: int = 50) -> str:
        if not items:
            return "_(none)_\n"
        lines = [f"- `{p}`" for p in items[:limit]]
        if len(items) > limit:
            lines.append(f"- … +{len(items) - limit} more")
        return "\n".join(lines) + "\n"

    body = f"""## Summary
PLATE template payload import plan for human review (Epic #615 / Feature #622).
Strategy: `{data.get('strategy')}` · Mode: `{'apply' if data.get('apply_mode') else 'dry-run'}`.
Target: `{data.get('target_dir')}` · Source: `{data.get('template_source')}`.

Counts: would_create={counts.get('would_create', 0)}, would_skip={counts.get('would_skip', 0)}, \
would_conflict={counts.get('would_conflict', 0)}, would_overwrite={counts.get('would_overwrite', 0)}.

## Payload additions
{_bullets(creates)}
## Preserved user files
{_bullets(skips)}
## Conflicts requiring judgment
{_bullets(conflicts)}
## Suggested renames/merges
"""
    renamed = [
        f
        for f in (data.get("files") or [])
        if isinstance(f, dict)
        and f.get("target_path")
        and f.get("target_path") != f.get("path")
    ]
    if renamed:
        for f in renamed[:40]:
            body += f"- `{f.get('path')}` → `{f.get('target_path')}` ({f.get('action')})\n"
    else:
        body += "_(none in plan)_\n"
    if overwrites:
        body += "\n## Force overwrites (only if intentional)\n"
        body += _bullets(overwrites)
    body += """
## Human review checklist
- [ ] No silent overwrite of product CI, package.json, CODEOWNERS, or root product docs without approval
- [ ] Conflicts listed above have an explicit keep/merge/rename decision
- [ ] PLATE methodology files land under expected paths (`scripts/plate/` when namespaced)
- [ ] `gh plate health` planned after merge
- [ ] Risk-sensitive paths (AGENTS.md, workflows, secrets, SPEC.md) reviewed if touched

## Links
- Epic #615 · Feature #622 · adoption guide `docs/migration/adoption-guide.md`
- AGENTS.md authority: humans keep judgment on high-risk merges
- Follow-up: `gh plate bootstrap --adopt` after safe payload land
"""
    return body


def write_import_escape_hatch(
    report: dict[str, Any] | ImportPayloadReport,
    dest_dir: str | Path,
) -> dict[str, Any]:
    """Write plan.json + PLAN.md + DRAFT_PR_BODY.md for hard-merge review (#622).

    Never applies payload files. Callers may open a draft PR from DRAFT_PR_BODY.md.
    """
    data = report.to_dict() if isinstance(report, ImportPayloadReport) else dict(report)
    out = Path(dest_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan_json = out / "plan.json"
    plan_md = out / "PLAN.md"
    draft_body = out / "DRAFT_PR_BODY.md"
    plan_json.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plan_md.write_text(render_import_plan_markdown(data), encoding="utf-8")
    draft_body.write_text(render_import_draft_pr_body(data), encoding="utf-8")
    return {
        "ok": True,
        "dir": str(out.resolve()),
        "plan_json": str(plan_json.resolve()),
        "plan_md": str(plan_md.resolve()),
        "draft_pr_body": str(draft_body.resolve()),
        "has_conflicts": bool(data.get("would_conflict") or data.get("conflicts")),
        "human_approval_required": True,
        "notes": [
            "Escape hatch does not write payload files.",
            "Open a draft PR with DRAFT_PR_BODY.md when conflicts need multi-file review.",
            "Never force-overwrite high-value product paths without explicit human approval.",
        ],
    }


def import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    dry_run: bool = True,
    apply: bool = False,
    namespace_scripts: bool | None = None,
    namespace_docs: bool | None = None,
    platform: str | None = None,
    escape_hatch_dir: str | Path | None = None,
    escape_hatch_on_conflict: bool = False,
) -> dict[str, Any]:
    """Public entry: dry-run by default; set apply=True (or dry_run=False) to write.

    ``escape_hatch_dir`` (#622): always write plan/PR-body bundle under this directory.
    ``escape_hatch_on_conflict``: when True and conflicts exist, write bundle under
    ``escape_hatch_dir`` or default ``.agentic/import-escape-hatch`` inside target.
    """
    do_apply = bool(apply) or (dry_run is False)
    report = plan_import_payload(
        target_dir,
        strategy=strategy,
        template_repo=template_repo,
        apply=do_apply,
        namespace_scripts=namespace_scripts,
        namespace_docs=namespace_docs,
        platform=platform,
    )
    data = report.to_dict()
    hatch_dir: Path | None = None
    if escape_hatch_dir is not None:
        hatch_dir = Path(escape_hatch_dir)
    elif escape_hatch_on_conflict and (
        data.get("would_conflict") or data.get("conflicts")
    ):
        hatch_dir = Path(target_dir) / ".agentic" / "import-escape-hatch"
    if hatch_dir is not None:
        data["escape_hatch"] = write_import_escape_hatch(data, hatch_dir)
    return data
