"""Release + marketplace packaging with media and adoption proof (#652).

Every package build aggregates:
- Approved GIFs/videos for changed behaviors (#635 / #636)
- Generated end-user narratives from Feature fragments + optional Q&A
- Simple "install this and start the first Q&A" onboarding proof
- Traceable links back to planning artifacts (issues, fragments, plans)

Publish remains human-gated (Tasks #380/#381/#626). Dry-run is default.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .release_media import (
    build_media_manifest,
    collect_release_media,
    media_approval_summary,
    render_media_markdown,
)

PACKAGING_DIR = Path(".agentic/packaging")
PACKAGES_FILE = "packages.json"
MARKER_BEGIN = "<!-- PLATE-PACKAGING:BEGIN -->"
MARKER_END = "<!-- PLATE-PACKAGING:END -->"

ONBOARDING_STEPS = [
    "Install: `pip install plate-core=={version}` (or pin via gh-plate VERSION).",
    "Extension: ensure `gh plate` resolves (monorepo checkout or published gh-plate tag).",
    "Bootstrap (optional): `gh plate bootstrap --apply` in the target repo.",
    "Config: `gh plate config init` if `.plate` is missing.",
    "First Q&A: open or create a Question; run `gh plate feed` or `plate_feed`.",
    "Plan: `gh plate plan --start` or `plate_planning_start` for product/feature intent.",
    "What next: `gh plate` / `plate_what_next` for the next process step.",
]


@dataclass
class PackageBuild:
    id: str
    version: str
    status: str = "draft"  # draft | ready | pending_publish_approval | approved_for_publish | published | cancelled
    created_at: str = ""
    updated_at: str = ""
    media_summary: dict[str, Any] = field(default_factory=dict)
    narratives: list[dict[str, Any]] = field(default_factory=list)
    onboarding_proof: dict[str, Any] = field(default_factory=dict)
    planning_links: list[str] = field(default_factory=list)
    fragment_slugs: list[str] = field(default_factory=list)
    readiness: dict[str, Any] = field(default_factory=dict)
    marketplace_entry: dict[str, Any] = field(default_factory=dict)
    publish_blocked_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or PACKAGING_DIR
    if d.name == PACKAGES_FILE:
        return d
    return d / PACKAGES_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "packages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "packages": []}
        data.setdefault("version", 1)
        data.setdefault("packages", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "packages": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_packaging_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def _slug_version(version: str) -> str:
    v = version.lstrip("v").strip() or "0.0.0"
    return re.sub(r"[^0-9A-Za-z._-]+", "-", v)


def _issue_links_from_fragment(frag: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for link in frag.get("links") or []:
        s = str(link).strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("http") or re.match(r"^\d+$", s):
            links.append(s if s.startswith("#") or s.startswith("http") else f"#{s}")
        else:
            links.append(s)
    return links


def narrative_for_fragment(frag: dict[str, Any]) -> dict[str, Any]:
    """Turn a release fragment into an end-user narrative bullet."""
    slug = str(frag.get("slug") or frag.get("_source_file") or "change")
    change_type = str(frag.get("change_type") or "docs")
    summary = str(frag.get("summary") or "").strip()
    surface = str(frag.get("surface") or "").strip()
    agent_notes = str(frag.get("agent_notes") or "").strip()
    links = _issue_links_from_fragment(frag)

    # Prefer human-facing summary; fall back to agent notes truncated.
    if summary:
        user_line = summary
        # Soft rewrite: drop internal-only prefixes when present
        user_line = re.sub(r"^(Harden|Wire|Deepen|First slice of)\s+", "", user_line, flags=re.I)
    elif agent_notes:
        user_line = agent_notes.split(".")[0].strip() + "."
    else:
        user_line = f"{change_type.title()} change on {surface or 'PLATE surfaces'}."

    what_it_means = (
        f"For end users: {user_line}"
        if not user_line.lower().startswith("for end users")
        else user_line
    )

    return {
        "slug": slug,
        "change_type": change_type,
        "surface": surface,
        "what_it_means": what_it_means,
        "links": links,
        "media_count": len(frag.get("media") or []),
        "planning_artifacts": links,
    }


def build_user_narratives(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [narrative_for_fragment(f) for f in fragments]


def build_onboarding_proof(
    version: str,
    *,
    include_feed: bool = True,
    include_planning: bool = True,
) -> dict[str, Any]:
    """Simple install → first Q&A proof checklist for marketplace/adoption."""
    ver = version.lstrip("v") or "0.0.0"
    steps = [s.format(version=ver) for s in ONBOARDING_STEPS]
    if not include_feed:
        steps = [s for s in steps if "feed" not in s.lower()]
    if not include_planning:
        steps = [s for s in steps if "plan" not in s.lower()]
    return {
        "version": ver,
        "title": "Install this and start the first Q&A",
        "steps": steps,
        "success_signal": (
            "Operator can run `gh plate feed` (or plate_feed) and see ranked "
            "Questions/Tasks without errors; optional plan session starts cleanly."
        ),
        "proof_commands": [
            f"pip install 'plate-core=={ver}'",
            "gh plate --help",
            "gh plate feed --json",
            "gh plate config show",
        ],
        "related_issues": ["#652", "#635", "#636", "#631", "#654"],
    }


def collect_planning_links(fragments: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in fragments:
        for link in _issue_links_from_fragment(f):
            if link not in seen:
                seen.add(link)
                out.append(link)
        slug = f.get("slug")
        if slug:
            frag_ref = f"fragment:{slug}"
            if frag_ref not in seen:
                seen.add(frag_ref)
                out.append(frag_ref)
    return out


def assess_package_readiness(
    *,
    media: list[dict[str, Any]],
    narratives: list[dict[str, Any]],
    onboarding: dict[str, Any],
    require_approved_media: bool = False,
) -> dict[str, Any]:
    """Gate package readiness. Publish always remains human-blocked."""
    summary = media_approval_summary(media)
    n_pending = int(summary.get("n_pending") or 0)
    n_approved = int(summary.get("n_approved") or 0)
    n_total = int(summary.get("n_total") or 0)

    blockers: list[str] = []
    warnings: list[str] = []

    if not narratives:
        blockers.append("no_fragments_or_narratives")
    if not (onboarding.get("steps") or []):
        blockers.append("missing_onboarding_steps")
    if require_approved_media and n_total > 0 and n_approved == 0:
        blockers.append("no_approved_media")
    if n_pending > 0:
        warnings.append(f"{n_pending}_media_pending_approval")
    if n_total == 0:
        warnings.append("no_media_attached")

    # Real-world publish is never auto-ready
    blockers.append("human_publish_task_required")

    ready_for_review = len([b for b in blockers if b != "human_publish_task_required"]) == 0
    return {
        "ready_for_review": ready_for_review,
        "ready_to_publish": False,  # always false until human Task completes
        "blockers": blockers,
        "warnings": warnings,
        "media_summary": summary,
        "narrative_count": len(narratives),
        "onboarding_step_count": len(onboarding.get("steps") or []),
    }


def build_marketplace_entry(
    version: str,
    *,
    narratives: list[dict[str, Any]],
    media_md: str,
    onboarding: dict[str, Any],
    planning_links: list[str],
) -> dict[str, Any]:
    ver = version.lstrip("v")
    highlights = [n["what_it_means"] for n in narratives[:12]]
    return {
        "name": "plate",
        "display_name": "PLATE",
        "version": ver,
        "summary": (
            f"PLATE {ver}: GitHub-native process engine with Q&A feed, "
            "autonomy gates, and release media."
        ),
        "highlights": highlights,
        "media_markdown": media_md,
        "onboarding": onboarding,
        "planning_links": planning_links[:40],
        "install": {
            "pip": f"pip install plate-core=={ver}",
            "gh_extension": "gh extension install akasper/gh-plate  # or monorepo checkout",
            "first_command": "gh plate feed",
        },
        "publish_note": (
            "Real marketplace/PyPI publish requires human Tasks "
            "(#380/#381/#625/#626). Agents prepare artifacts only."
        ),
    }


# Heuristic packaging cost (#634/#652) — advisory tokens for build + review packets.
_PACKAGE_ESTIMATE_BASE = 6000
_PACKAGE_MEDIA_EXTRA = 2000
_PACKAGE_PERSIST_EXTRA = 1500


def estimate_package_cost(
    *,
    n_fragments: int = 0,
    n_media: int = 0,
    persist: bool = True,
) -> dict[str, Any]:
    """Advisory token estimate for marketplace package build (#634/#652)."""
    tokens = _PACKAGE_ESTIMATE_BASE
    frag_n = max(0, int(n_fragments or 0))
    media_n = max(0, int(n_media or 0))
    tokens += min(8000, frag_n * 200)
    if media_n:
        tokens += _PACKAGE_MEDIA_EXTRA + min(4000, media_n * 300)
    if persist:
        tokens += _PACKAGE_PERSIST_EXTRA
    return {
        "ok": True,
        "estimated_tokens": int(tokens),
        "breakdown": {
            "base": _PACKAGE_ESTIMATE_BASE,
            "fragments": min(8000, frag_n * 200),
            "media": (_PACKAGE_MEDIA_EXTRA + min(4000, media_n * 300)) if media_n else 0,
            "persist": _PACKAGE_PERSIST_EXTRA if persist else 0,
        },
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine enforce hard ceilings.",
            "build_package hydrates remaining via get_budget_snapshot when use_live_budget.",
            "Human marketplace publish remains a Task (#380/#381/#626) — never auto-publish.",
        ],
    }


def build_package(
    version: str,
    fragments: list[dict[str, Any]],
    *,
    base_dir: Path | None = None,
    require_approved_media: bool = False,
    persist: bool = True,
    package_id: str | None = None,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Build a full marketplace/release package payload (dry-run safe).

    #634: when ``budget_remaining`` is omitted and ``use_live_budget`` is True (default),
    hydrate remaining tokens from durable budget snapshot and block if est exceeds remaining.
    Never auto-publishes (human Tasks for real marketplace publish).
    """
    frags = list(fragments or [])
    n_media = 0
    for f in frags:
        media = f.get("media") if isinstance(f, dict) else None
        if isinstance(media, list):
            n_media += len(media)
    cost_est = estimate_package_cost(
        n_fragments=len(frags), n_media=n_media, persist=persist
    )
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    effective_remaining = budget_remaining
    budget_notes: list[str] = []
    if effective_remaining is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(estimate_tokens=est_tokens)
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective_remaining = int(rem)
                budget_notes.append(
                    f"budget hydrated: remaining_tokens={effective_remaining} "
                    f"pressure={snap.get('budget_pressure')}"
                )
        except Exception as exc:
            budget_notes.append(f"budget hydrate skipped: {exc}")

    if effective_remaining is not None and est_tokens > int(effective_remaining):
        return {
            "ok": False,
            "blocked": True,
            "reason": "budget",
            "error": (
                f"budget: est {est_tokens} tokens exceeds remaining {effective_remaining}"
            ),
            "cost_estimate_tokens": est_tokens,
            "budget_remaining": int(effective_remaining),
            "cost_estimate": cost_est,
            "notes": budget_notes,
        }

    ver = version.lstrip("v") or "0.0.0"
    media_manifest = build_media_manifest(frags, version=ver)
    media = list(media_manifest.get("media") or [])
    narratives = build_user_narratives(frags)
    onboarding = build_onboarding_proof(ver)
    planning_links = collect_planning_links(frags)
    media_md = str(media_manifest.get("markdown_approved") or "") or render_media_markdown(
        media, only_approved=True
    )
    readiness = assess_package_readiness(
        media=media,
        narratives=narratives,
        onboarding=onboarding,
        require_approved_media=require_approved_media,
    )
    marketplace = build_marketplace_entry(
        ver,
        narratives=narratives,
        media_md=media_md,
        onboarding=onboarding,
        planning_links=planning_links,
    )

    pid = package_id or f"pkg-{_slug_version(ver)}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    now = _now()
    status = "ready" if readiness["ready_for_review"] else "draft"
    if readiness["ready_for_review"]:
        status = "pending_publish_approval"

    pkg = PackageBuild(
        id=pid,
        version=ver,
        status=status,
        created_at=now,
        updated_at=now,
        media_summary=media_manifest.get("summary") or {},
        narratives=narratives,
        onboarding_proof=onboarding,
        planning_links=planning_links,
        fragment_slugs=[str(f.get("slug") or f.get("_source_file") or "") for f in frags],
        readiness=readiness,
        marketplace_entry=marketplace,
        publish_blocked_reason="human_publish_task_required",
        metadata={
            "media_markdown_all": media_manifest.get("markdown_all") or "",
            "media_markdown_approved": media_md,
            "require_approved_media": require_approved_media,
            "cost_estimate_tokens": est_tokens,
            "budget_remaining": effective_remaining,
            "budget_notes": budget_notes,
        },
    )

    if persist:
        data = _load(base_dir)
        packages = list(data.get("packages") or [])
        packages = [p for p in packages if p.get("id") != pid]
        packages.append(pkg.to_dict())
        data["packages"] = packages[-50:]  # cap history
        _save(data, base_dir)

    out: dict[str, Any] = {
        "ok": True,
        "package": pkg.to_dict(),
        "cost_estimate_tokens": est_tokens,
        "budget_remaining": effective_remaining,
        "cost_estimate": cost_est,
        "notes": list(budget_notes),
        "marker": render_packaging_marker(
            {
                "id": pid,
                "version": ver,
                "status": status,
                "ready_for_review": readiness["ready_for_review"],
                "n_narratives": len(narratives),
                "n_media": int((media_manifest.get("summary") or {}).get("n_total") or 0),
                "cost_estimate_tokens": est_tokens,
            }
        ),
    }
    try:
        from .autonomy import apply_live_budget_charge

        apply_live_budget_charge(
            out,
            tokens=est_tokens,
            use_live_budget=use_live_budget,
            action_kind="package_build",
            reason=f"build_package:{ver}:{pid}",
        )
    except Exception:
        pass
    return out


def list_packages(
    *,
    base_dir: Path | None = None,
    status: str = "all",
    limit: int = 20,
) -> list[dict[str, Any]]:
    data = _load(base_dir)
    rows = list(data.get("packages") or [])
    if status and status != "all":
        rows = [p for p in rows if p.get("status") == status]
    rows.sort(key=lambda p: str(p.get("updated_at") or p.get("created_at") or ""), reverse=True)
    return rows[: max(1, int(limit))]


def get_package(package_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for p in list_packages(base_dir=base_dir, status="all", limit=200):
        if p.get("id") == package_id:
            return p
    return None


def decide_package_publish(
    package_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str = "",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Approve package *for human publish* or reject. Never publishes."""
    data = _load(base_dir)
    packages = list(data.get("packages") or [])
    found = None
    for i, p in enumerate(packages):
        if p.get("id") == package_id:
            found = (i, p)
            break
    if not found:
        return {"ok": False, "error": f"package not found: {package_id}"}

    idx, pkg = found
    d = (decision or "").strip().lower()
    now = _now()
    if d in ("approve", "approved", "approve_publish"):
        if not (pkg.get("readiness") or {}).get("ready_for_review"):
            return {
                "ok": False,
                "error": "package not ready_for_review",
                "package": pkg,
            }
        pkg["status"] = "approved_for_publish"
        pkg["publish_blocked_reason"] = (
            "Open/complete human Task for marketplace/PyPI publish; agent will not publish."
        )
    elif d in ("reject", "rejected", "cancel", "cancelled"):
        pkg["status"] = "cancelled"
        pkg["publish_blocked_reason"] = note or "rejected_by_user"
    else:
        return {"ok": False, "error": f"unknown decision: {decision}"}

    pkg["updated_at"] = now
    meta = dict(pkg.get("metadata") or {})
    meta["last_decision"] = {
        "decision": d,
        "decided_by": decided_by,
        "note": note,
        "at": now,
    }
    pkg["metadata"] = meta
    packages[idx] = pkg
    data["packages"] = packages
    _save(data, base_dir)
    return {
        "ok": True,
        "package": pkg,
        "note": "Publish still requires human Task; this only marks package approval.",
    }


def render_package_markdown(package: dict[str, Any]) -> str:
    """Human-readable marketplace/release packaging document."""
    ver = package.get("version") or "?"
    entry = package.get("marketplace_entry") or {}
    lines = [
        f"# PLATE marketplace package v{ver}",
        "",
        str(entry.get("summary") or f"PLATE {ver} package."),
        "",
        f"**Status:** {package.get('status')}",
        f"**Ready for review:** {(package.get('readiness') or {}).get('ready_for_review')}",
        "**Ready to publish:** false (human Task required)",
        "",
        "## What this means for end users",
        "",
    ]
    for n in package.get("narratives") or []:
        line = n.get("what_it_means") or n.get("slug")
        links = n.get("links") or []
        link_s = f" ({', '.join(links)})" if links else ""
        lines.append(f"- {line}{link_s}")
    lines.append("")

    media_md = (package.get("metadata") or {}).get("media_markdown_approved") or ""
    if media_md.strip():
        lines.append("## Approved demo media")
        lines.append("")
        lines.append(media_md.rstrip())
        lines.append("")

    onb = package.get("onboarding_proof") or {}
    lines.append(f"## {onb.get('title') or 'Onboarding proof'}")
    lines.append("")
    for i, step in enumerate(onb.get("steps") or [], 1):
        lines.append(f"{i}. {step}")
    lines.append("")
    if onb.get("success_signal"):
        lines.append(f"**Success signal:** {onb['success_signal']}")
        lines.append("")
    cmds = onb.get("proof_commands") or []
    if cmds:
        lines.append("**Proof commands:**")
        lines.append("")
        lines.append("```bash")
        lines.extend(cmds)
        lines.append("```")
        lines.append("")

    links = package.get("planning_links") or []
    if links:
        lines.append("## Planning artifacts")
        lines.append("")
        for link in links[:40]:
            lines.append(f"- {link}")
        lines.append("")

    readiness = package.get("readiness") or {}
    if readiness.get("blockers") or readiness.get("warnings"):
        lines.append("## Readiness")
        lines.append("")
        if readiness.get("blockers"):
            lines.append(f"- Blockers: {', '.join(readiness['blockers'])}")
        if readiness.get("warnings"):
            lines.append(f"- Warnings: {', '.join(readiness['warnings'])}")
        lines.append("")

    if entry.get("publish_note"):
        lines.append(str(entry["publish_note"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def packaging_feed_items(
    *,
    base_dir: Path | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Endless-feed items for packages awaiting publish approval."""
    items: list[dict[str, Any]] = []
    for p in list_packages(base_dir=base_dir, status="all", limit=50):
        st = p.get("status")
        if st not in ("pending_publish_approval", "ready", "approved_for_publish"):
            continue
        pid = p.get("id")
        ver = p.get("version")
        if st == "approved_for_publish":
            items.append(
                {
                    "id": f"packaging-{pid}",
                    "item_type": "packaging",
                    "title": f"Package v{ver} approved — complete human publish Task",
                    "rank": 16,
                    "impact": "critical",
                    "badges": ["packaging", "human_task", f"v{ver}"],
                    "source": "packaging",
                    "reason": "Marketplace package approved; real publish is human-only (#652)",
                    "prompt_segment": (
                        f"Package {pid} v{ver} approved_for_publish. "
                        "Do not publish as agent. Complete Tasks #380/#381/#626 or open via plate_task_detect."
                    ),
                    "ask_user_question": {
                        "question": f"Package v{ver} is approved. Human publish next?",
                        "options": [
                            {
                                "id": "open_task",
                                "label": "Open/confirm human publish Task",
                                "description": "plate_task_detect marketplace/PyPI create=true",
                            },
                            {
                                "id": "later",
                                "label": "Leave for later",
                                "description": "Keep package approved_for_publish",
                            },
                        ],
                    },
                    "package_id": pid,
                    "version": ver,
                }
            )
        else:
            items.append(
                {
                    "id": f"packaging-{pid}",
                    "item_type": "packaging",
                    "title": f"Marketplace package v{ver} ready for review",
                    "rank": 16,
                    "impact": "high",
                    "badges": ["packaging", "media", "onboarding", f"v{ver}"],
                    "source": "packaging",
                    "reason": "Package includes media + narratives + onboarding proof (#652)",
                    "prompt_segment": (
                        f"Review package {pid}: plate_packaging_get / gh plate packaging --get. "
                        f"Approve for human publish: plate_packaging_decide {pid} approve."
                    ),
                    "ask_user_question": {
                        "question": f"Marketplace entry for v{ver} ready (media + proof). Approve publish via PM?",
                        "options": [
                            {
                                "id": "approve",
                                "label": "Approve for human publish",
                                "description": f"plate_packaging_decide {pid} approve",
                            },
                            {
                                "id": "reject",
                                "label": "Reject package",
                                "description": f"plate_packaging_decide {pid} reject",
                            },
                            {
                                "id": "rebuild",
                                "label": "Rebuild with latest fragments",
                                "description": "plate_packaging_build",
                            },
                        ],
                    },
                    "package_id": pid,
                    "version": ver,
                }
            )
        if len(items) >= limit:
            break
    return items


def plan_marketplace_package_op(
    version: str | None = None,
    *,
    fragments: list[dict[str, Any]] | None = None,
    releases_dir: Path | str = ".agentic/releases",
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Agent packet for scheduled marketplace-package op (#641/#652).

    Includes #634 cost estimate; build preview respects budget gate (persist=False).
    """
    from .release import collect_fragments

    frags = fragments
    if frags is None:
        frags = collect_fragments(Path(releases_dir))
    ver = (version or "unreleased").lstrip("v")
    n_media = 0
    for f in frags or []:
        media = f.get("media") if isinstance(f, dict) else None
        if isinstance(media, list):
            n_media += len(media)
    cost_est = estimate_package_cost(
        n_fragments=len(frags or []), n_media=n_media, persist=True
    )
    built = build_package(
        ver,
        frags,
        persist=False,
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
    pkg = built.get("package") or {}
    out: dict[str, Any] = {
        "ok": bool(built.get("ok")),
        "op_id": "marketplace-package",
        "version": ver,
        "cost_estimate": cost_est,
        "cost_estimate_tokens": cost_est.get("estimated_tokens"),
        "budget_remaining": built.get("budget_remaining"),
        "package_preview": {
            "status": pkg.get("status"),
            "readiness": pkg.get("readiness"),
            "n_narratives": len(pkg.get("narratives") or []),
            "media_summary": pkg.get("media_summary"),
            "onboarding_title": (pkg.get("onboarding_proof") or {}).get("title"),
        },
        "steps": [
            "Check budget: plate_autonomy_budget / remaining vs cost_estimate_tokens",
            "plate_packaging_build (persist package under .agentic/packaging/)",
            "Review markdown: plate_packaging_render",
            "Surface feed: plate_packaging_feed / endless feed",
            "On approve: plate_packaging_decide approve (still no auto-publish)",
            "plate_task_detect marketplace/PyPI — open human Task if needed",
            "Human completes publish; agent never holds marketplace credentials",
        ],
        "tools": [
            "plate_autonomy_budget",
            "plate_packaging_build",
            "plate_packaging_decide",
            "plate_packaging_feed",
            "plate_task_detect",
            "plate_task_create",
        ],
        "ask_user_question": {
            "question": f"Build marketplace package for v{ver} (media + adoption proof)?",
            "options": [
                {
                    "id": "build",
                    "label": "Build package artifacts",
                    "description": "plate_packaging_build",
                },
                {
                    "id": "skip",
                    "label": "Skip this cycle",
                    "description": "No package written",
                },
            ],
        },
        "marker": render_packaging_marker(
            {
                "op": "marketplace-package",
                "version": ver,
                "cost_estimate_tokens": cost_est.get("estimated_tokens"),
            }
        ),
    }
    if not built.get("ok"):
        out["blocked"] = True
        out["error"] = built.get("error")
        out["reason"] = built.get("reason")
        out["package_preview"] = {"blocked": True, "error": built.get("error")}
    return out
