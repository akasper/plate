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
    resolve_template_source,
    should_include_template_file,
)

Strategy = Literal["safe", "conservative", "force"]
VALID_STRATEGIES: tuple[str, ...] = ("safe", "conservative", "force")


@dataclass
class PayloadFileDecision:
    path: str
    action: str  # create | skip | conflict | overwrite
    classification: str
    detail: str = ""

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
) -> PayloadFileDecision:
    if not dest.exists():
        return PayloadFileDecision(
            path=rel,
            action="create",
            classification=classification,
            detail="missing at target",
        )

    # Existing path
    identical = False
    if dest.is_file() and source.is_file():
        try:
            identical = _file_sha256(dest) == _file_sha256(source)
        except OSError:
            identical = False

    if identical:
        return PayloadFileDecision(
            path=rel,
            action="skip",
            classification=classification,
            detail="identical content",
        )

    if strategy == "force":
        return PayloadFileDecision(
            path=rel,
            action="overwrite",
            classification=classification,
            detail="existing differs; force overwrites",
        )

    if strategy == "conservative":
        return PayloadFileDecision(
            path=rel,
            action="conflict",
            classification=classification,
            detail="existing differs; conservative never overwrites",
        )

    # safe: skip any existing path without treating as hard conflict
    return PayloadFileDecision(
        path=rel,
        action="skip",
        classification=classification,
        detail="exists at target (safe strategy skips)",
    )


def _next_steps(report: ImportPayloadReport) -> list[str]:
    steps = [
        "Review would_create / would_conflict lists before --apply on real repos.",
        "After local apply: commit scaffolding, run `gh plate bootstrap --apply` for labels/wiki/.plate GitHub-side setup.",
        "Run `gh plate health` and open the first Curiosity Q&A session when healthy.",
    ]
    if report.would_conflict or report.conflicts:
        steps.insert(
            0,
            "Resolve would_conflict paths manually or re-run with --strategy force only if intentional overwrite is desired.",
        )
    if report.apply_mode and (report.created or report.overwritten):
        steps.insert(0, "git status + review diffs for newly written payload files.")
    return steps


def plan_import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    apply: bool = False,
) -> ImportPayloadReport:
    """Plan (and optionally apply) template payload import into a local target dir."""
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

    manifest = load_template_payload_manifest()
    rel_paths = list_payload_relative_paths(template_root)
    report = ImportPayloadReport(
        apply_mode=bool(apply),
        strategy=strat,
        target_dir=str(target),
        template_source=source_kind,
        template_root=str(template_root),
    )

    for rel in rel_paths:
        source = template_root / rel
        dest = target / rel
        classification = classify_template_file(rel, manifest)
        decision = _decide_file(
            rel=rel,
            source=source,
            dest=dest,
            strategy=strat,  # type: ignore[arg-type]
            classification=classification,
        )
        report.files.append(decision)

        if decision.action == "create":
            report.would_create.append(rel)
            if apply:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                report.created.append(rel)
        elif decision.action == "overwrite":
            report.would_overwrite.append(rel)
            if apply:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                report.overwritten.append(rel)
        elif decision.action == "conflict":
            report.would_conflict.append(rel)
            if apply:
                report.conflicts.append(rel)
        else:
            report.would_skip.append(rel)
            if apply:
                report.skipped.append(rel)

    report.next_steps = _next_steps(report)
    return report


def import_payload(
    target_dir: str | Path = ".",
    *,
    strategy: str = "safe",
    template_repo: str | None = None,
    dry_run: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    """Public entry: dry-run by default; set apply=True (or dry_run=False) to write."""
    do_apply = bool(apply) or (dry_run is False)
    report = plan_import_payload(
        target_dir,
        strategy=strategy,
        template_repo=template_repo,
        apply=do_apply,
    )
    return report.to_dict()


def copy_template_payload_local(
    dest_root: str | Path,
    *,
    source_root: str | Path | None = None,
    strategy: str = "safe",
    dry_run: bool = True,
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
