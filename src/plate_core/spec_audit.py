"""SPEC.md vs implemented-evidence audit engine (#338 / Epic SPEC auditing).

v1 focuses on structured findings for agent/CLI consumption:
- ``undocumented``: implemented fragments/surfaces not reflected in SPEC text
- ``aligned``: fragment surfaces mentioned in SPEC
- ``stale_evidence``: SPEC text cites paths that do not exist on disk
- ``future_ok``: SPEC sections without implementation (not an error per planning rules)

Evidence sources (v1): unreleased release fragments + local filesystem path probes.
Prefer tests/workflows later (#339); this slice is the audit data plane only.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FINDING_KINDS = (
    "aligned",
    "undocumented",
    "stale_evidence",
    "future_ok",
    "conflict",
)


@dataclass
class SpecFinding:
    kind: str
    title: str
    confidence: str  # high | medium | low
    evidence: list[str] = field(default_factory=list)
    section: str | None = None
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpecAuditReport:
    ok: bool
    repo_root: str
    spec_path: str
    findings: list[SpecFinding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "repo_root": self.repo_root,
            "spec_path": self.spec_path,
            "counts": dict(self.counts),
            "notes": list(self.notes),
            "findings": [f.to_dict() for f in self.findings],
        }


def _normalize_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9_./-]{2,}", text.lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "when",
        "into",
        "via",
        "are",
        "was",
        "has",
        "not",
        "use",
        "using",
        "under",
        "must",
        "should",
        "will",
        "can",
        "may",
        "per",
        "see",
        "json",
        "md",
        "yml",
        "true",
        "false",
    }
    return {w for w in words if w not in stop and not w.isdigit()}


def extract_spec_headings(spec_text: str) -> list[str]:
    """Return markdown headings (## / ###) for section provenance."""
    heads: list[str] = []
    for line in spec_text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if m:
            heads.append(m.group(2).strip())
    return heads


def extract_path_citations(spec_text: str) -> list[str]:
    """Heuristic paths cited in SPEC (backticked or bare relative paths)."""
    paths: list[str] = []
    for m in re.finditer(r"`([^`\n]+)`", spec_text):
        p = m.group(1).strip()
        if "/" in p or p.startswith(".") or p.endswith((".md", ".yml", ".yaml", ".py", ".json")):
            if " " not in p and not p.startswith("http"):
                paths.append(p)
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _surface_modules(surface: str) -> list[str]:
    parts = re.split(r"[,;]", surface or "")
    mods: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        mods.append(p)
        # also stem for matching
        if "/" in p:
            mods.append(p.split("/")[-1])
        if p.endswith(".py"):
            mods.append(Path(p).stem)
    return mods


def audit_spec(
    repo_root: str | Path | None = None,
    *,
    releases_dir: str | Path | None = None,
    spec_path: str | Path | None = None,
) -> SpecAuditReport:
    """Run SPEC audit against fragments + filesystem evidence."""
    root = Path(repo_root or ".").resolve()
    spec_file = Path(spec_path) if spec_path else root / "SPEC.md"
    rel_dir = Path(releases_dir) if releases_dir else root / ".agentic" / "releases"

    if not spec_file.is_file():
        return SpecAuditReport(
            ok=False,
            repo_root=str(root),
            spec_path=str(spec_file),
            error=f"SPEC.md not found at {spec_file}",
        )

    try:
        spec_text = spec_file.read_text(encoding="utf-8")
    except OSError as exc:
        return SpecAuditReport(
            ok=False,
            repo_root=str(root),
            spec_path=str(spec_file),
            error=str(exc),
        )

    findings: list[SpecFinding] = []
    headings = extract_spec_headings(spec_text)
    spec_tokens = _normalize_tokens(spec_text)
    citations = extract_path_citations(spec_text)

    # Stale path citations
    for cite in citations:
        # skip version placeholders and pure symbols
        if cite in {"SPEC.md", "AGENTS.md", "CURRENT.md"}:
            # existence check still useful
            pass
        candidate = root / cite
        # only check repo-relative file-like citations
        if any(ch in cite for ch in ("*", "{", "}")):
            continue
        if cite.startswith("gh ") or cite.startswith("plate_"):
            continue
        if "/" not in cite and not cite.startswith("."):
            # bare names like AutonomyEngine — skip filesystem probe
            if not cite.endswith((".md", ".yml", ".yaml", ".py", ".json", ".sh")):
                continue
        if not candidate.exists() and not (root / cite.lstrip("./")).exists():
            # Only flag if looks like a concrete path
            if "/" in cite or cite.startswith("."):
                findings.append(
                    SpecFinding(
                        kind="stale_evidence",
                        title=f"SPEC cites missing path: {cite}",
                        confidence="medium",
                        evidence=[f"SPEC citation `{cite}`", f"missing on disk under {root}"],
                        recommendation="Update SPEC evidence path or restore the artifact.",
                        metadata={"path": cite},
                    )
                )

    # Fragments as implemented evidence
    fragments: list[dict[str, Any]] = []
    try:
        from .release import collect_fragments

        if rel_dir.is_dir():
            fragments = collect_fragments(rel_dir)
    except Exception as exc:
        findings.append(
            SpecFinding(
                kind="conflict",
                title="Could not load release fragments",
                confidence="low",
                evidence=[str(exc)],
                recommendation="Ensure .agentic/releases/ is readable.",
            )
        )

    undocumented = 0
    aligned = 0
    for frag in fragments:
        slug = str(frag.get("slug") or frag.get("id") or "fragment")
        summary = str(frag.get("summary") or "")
        surface = str(frag.get("surface") or "")
        change_type = str(frag.get("change_type") or "")
        # Only treat feature/process as strong implemented evidence for SPEC gaps
        if change_type not in ("feature", "process", "breaking", "fix"):
            continue
        modules = _surface_modules(surface)
        # Match if any distinctive module/path token appears in SPEC
        hit = False
        hit_ev: list[str] = []
        for mod in modules:
            token = mod.lower().replace("src/", "")
            if len(token) < 4:
                continue
            if token in spec_text.lower() or token.replace(".py", "") in spec_tokens:
                hit = True
                hit_ev.append(f"surface match: {mod}")
                break
        # also try slug keywords
        if not hit:
            for tok in _normalize_tokens(slug.replace("-", " ")):
                if len(tok) >= 6 and tok in spec_tokens:
                    hit = True
                    hit_ev.append(f"slug token in SPEC: {tok}")
                    break
        if hit:
            aligned += 1
            findings.append(
                SpecFinding(
                    kind="aligned",
                    title=f"Fragment reflected in SPEC: {slug}",
                    confidence="medium",
                    evidence=[summary[:200], surface, *hit_ev],
                    recommendation="No action; keep SPEC/fragments in sync as work lands.",
                    metadata={"slug": slug, "change_type": change_type},
                )
            )
        else:
            undocumented += 1
            findings.append(
                SpecFinding(
                    kind="undocumented",
                    title=f"Implemented fragment not reflected in SPEC: {slug}",
                    confidence="medium",
                    evidence=[summary[:240], surface or "(no surface)"],
                    recommendation=(
                        "Consider Documentation PR to add this implemented+tested "
                        "behavior to SPEC (v1 prefers additive SPEC updates)."
                    ),
                    metadata={"slug": slug, "change_type": change_type, "links": frag.get("links")},
                )
            )

    # future_ok: SPEC has headings but zero fragments (repo without unreleased work)
    if not fragments and headings:
        findings.append(
            SpecFinding(
                kind="future_ok",
                title="SPEC present without unreleased fragments",
                confidence="high",
                evidence=[f"{len(headings)} SPEC headings", "no unreleased fragments"],
                recommendation="Not an error; future-state SPEC content is allowed.",
                section=headings[0] if headings else None,
            )
        )

    counts: dict[str, int] = {k: 0 for k in FINDING_KINDS}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1

    notes = [
        "v1 audit: fragments + path citations only; tests/workflows preference lands in follow-ups (#339).",
        "Absence of implementation for future-state SPEC is not an error (planning #335/#338).",
        f"SPEC headings: {len(headings)}; unreleased/epic fragments considered: {len(fragments)}.",
    ]

    return SpecAuditReport(
        ok=True,
        repo_root=str(root),
        spec_path=str(spec_file),
        findings=findings,
        counts=counts,
        notes=notes,
    )


def format_spec_audit_markdown(report: SpecAuditReport | dict[str, Any]) -> str:
    data = report.to_dict() if isinstance(report, SpecAuditReport) else report
    lines = [
        "## SPEC audit (#338)",
        f"- Root: {data.get('repo_root')}",
        f"- SPEC: {data.get('spec_path')}",
        f"- Counts: {data.get('counts')}",
    ]
    if data.get("error"):
        lines.append(f"- ERROR: {data.get('error')}")
    for note in data.get("notes") or []:
        lines.append(f"- Note: {note}")
    # prioritize undocumented and stale
    findings = data.get("findings") or []
    priority = [f for f in findings if f.get("kind") in ("undocumented", "stale_evidence", "conflict")]
    other = [f for f in findings if f not in priority]
    show = priority[:20] + other[:10]
    if show:
        lines.append("- Findings:")
        for f in show:
            lines.append(
                f"  - [{f.get('kind')}|{f.get('confidence')}] {f.get('title')}"
            )
    return "\n".join(lines) + "\n"
