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
    namespace_scripts: bool = False
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


def _next_steps(report: ImportPayloadReport) -> list[str]:
    steps = [
        "Review would_create / would_conflict lists before --apply on real repos.",
        "After local apply: commit scaffolding, run `gh plate bootstrap --apply` (or `--adopt`) for labels/wiki/.plate GitHub-side setup.",
        "Run `gh plate health` and open the first Curiosity Q&A session when healthy.",
        "Prefer `.agentic/releases/unreleased/` fragments for durable implemented-state; keep CURRENT.md as a short index (#618).",
    ]
    if report.would_conflict or report.conflicts:
        steps.insert(
            0,
            "Resolve would_conflict paths manually or re-run with --strategy force only if intentional overwrite is desired.",
        )
    if report.apply_mode and (report.created or report.overwritten):
        steps.insert(0, "git status + review diffs for newly written payload files.")
    if any(x == "CURRENT.md" or x.endswith("CURRENT.md") for x in report.would_create):
        steps.insert(
            0,
            "Fill CURRENT.md capability rows (or deprecate to fragments) once real features land.",
        )
    return steps


def plan_import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    apply: bool = False,
    namespace_scripts: bool | None = None,
) -> ImportPayloadReport:
    """Plan (and optionally apply) template payload import into a local target dir.

    ``namespace_scripts``: when True, install PLATE scripts under ``scripts/plate/``
    and rewrite workflow script refs (#621). None = auto-detect if target has a
    non-empty product ``scripts/`` tree.
    """
    from .payload_surface import (
        namespace_script_path,
        rewrite_workflow_script_refs,
        should_namespace_scripts,
    )

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

    manifest = load_template_payload_manifest()
    rel_paths = list_payload_relative_paths(template_root)
    report = ImportPayloadReport(
        apply_mode=bool(apply),
        strategy=strat,
        target_dir=str(target),
        template_source=source_kind,
        template_root=str(template_root),
        namespace_scripts=ns,
    )

    for rel in rel_paths:
        source = template_root / rel
        # Prefer namespaced install path for plate scripts when adopting (#621)
        preferred_rel = namespace_script_path(rel) if ns and rel.startswith("scripts/") else rel
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
        # Override target_path for namespaced scripts (path_rules install_as wins if set)
        if ns and rel.startswith("scripts/") and decision.action in (
            "create",
            "create_as",
            "overwrite",
            "skip",
            "conflict",
        ):
            if decision.action != "create_as" or not decision.target_path:
                decision.target_path = preferred_rel
            if preferred_rel != rel and decision.action == "create":
                decision.detail = (
                    f"{decision.detail}; namespaced to {preferred_rel} (#621)"
                    if decision.detail
                    else f"namespaced to {preferred_rel} (#621)"
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
                    data = source.read_bytes()
                    if ns and (
                        rel.startswith(".github/workflows/")
                        or write_rel.startswith(".github/workflows/")
                    ):
                        try:
                            text = data.decode("utf-8")
                            data = rewrite_workflow_script_refs(text).encode("utf-8")
                        except UnicodeDecodeError:
                            pass
                    write_dest.write_bytes(data)
                    report.created.append(label)
        elif decision.action == "overwrite":
            label = f"{rel} -> {write_rel}" if write_rel != rel else rel
            report.would_overwrite.append(label)
            if apply:
                write_dest.parent.mkdir(parents=True, exist_ok=True)
                data = source.read_bytes()
                if ns and (
                    rel.startswith(".github/workflows/")
                    or write_rel.startswith(".github/workflows/")
                ):
                    try:
                        text = data.decode("utf-8")
                        data = rewrite_workflow_script_refs(text).encode("utf-8")
                    except UnicodeDecodeError:
                        pass
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

    report.next_steps = _next_steps(report)
    if ns:
        report.next_steps.insert(
            0,
            "PLATE scripts install under scripts/plate/; workflows rewritten to match (#621).",
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


def import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    dry_run: bool = True,
    apply: bool = False,
    namespace_scripts: bool | None = None,
) -> dict[str, Any]:
    """Public entry: dry-run by default; set apply=True (or dry_run=False) to write."""
    do_apply = bool(apply) or (dry_run is False)
    report = plan_import_payload(
        target_dir,
        strategy=strategy,
        template_repo=template_repo,
        apply=do_apply,
        namespace_scripts=namespace_scripts,
    )
    return report.to_dict()


def copy_template_payload_local(
    dest_root: str | Path,
    *,
    source_root: str | Path | None = None,
    strategy: str = "safe",
    dry_run: bool = True,
    namespace_scripts: bool | None = None,
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
        f"- Payload files: {counts.get('payload_files', 0)}",
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
    steps = data.get("next_steps") or []
    if steps:
        lines.append("- Next steps:")
        for s in steps:
            lines.append(f"  - {s}")
    return "\n".join(lines) + "\n"
