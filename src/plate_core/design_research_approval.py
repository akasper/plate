"""Design / Research artifact approval surface (#632).

Surfaces Design docs/visuals and Research results for human approve / revise /
reject before they become authoritative for planning/implementation.

Durable proposals live under `.agentic/approvals/` with versioned decisions.
Host posts markers on linked issues; does not auto-merge design authority.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APPROVALS_DIR = Path(".agentic/approvals")
MARKER_BEGIN = "<!-- PLATE-ARTIFACT-APPROVAL:BEGIN -->"
MARKER_END = "<!-- PLATE-ARTIFACT-APPROVAL:END -->"
# Statuses that still need human action in the endless feed (#632 harden)
ACTIONABLE_STATUSES = frozenset({"pending", "revised"})


@dataclass
class ArtifactProposal:
    id: str
    kind: str  # design | research
    title: str
    summary: str
    content_path: str = ""  # path or URL to artifact
    content_excerpt: str = ""
    related_issue: int | None = None
    related_epic: int | None = None
    originating_question: int | None = None
    media_links: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | approved | revised | rejected
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    decided_by: str | None = None
    decision_note: str = ""
    actor: str = "agent"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactProposal":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure(base: Path | None = None) -> Path:
    d = base or APPROVALS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(pid: str, base: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", pid)
    return _ensure(base) / f"{safe}.json"


# Heuristic artifact proposal costs (#634/#632).
_ARTIFACT_BASE = 3500
_ARTIFACT_RESEARCH_EXTRA = 1500
_ARTIFACT_MEDIA_EACH = 200
_ARTIFACT_RESUBMIT = 2000


def estimate_artifact_cost(
    *,
    kind: str = "design",
    n_media: int = 0,
    resubmit: bool = False,
) -> dict[str, Any]:
    """Advisory token estimate for Design/Research artifact propose/resubmit (#634/#632)."""
    k = "research" if (kind or "").lower().startswith("res") else "design"
    tokens = _ARTIFACT_RESUBMIT if resubmit else _ARTIFACT_BASE
    if k == "research" and not resubmit:
        tokens += _ARTIFACT_RESEARCH_EXTRA
    media_n = max(0, int(n_media or 0))
    tokens += min(2000, media_n * _ARTIFACT_MEDIA_EACH)
    return {
        "ok": True,
        "kind": k,
        "estimated_tokens": int(tokens),
        "breakdown": {
            "base": _ARTIFACT_RESUBMIT if resubmit else _ARTIFACT_BASE,
            "research": _ARTIFACT_RESEARCH_EXTRA if (k == "research" and not resubmit) else 0,
            "media": min(2000, media_n * _ARTIFACT_MEDIA_EACH),
        },
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine enforce hard ceilings.",
            "propose_artifact / resubmit_proposal hydrate remaining when use_live_budget.",
        ],
    }


def _artifact_budget_gate(
    *,
    kind: str,
    n_media: int = 0,
    resubmit: bool = False,
    budget_remaining: int | None,
    use_live_budget: bool,
) -> tuple[dict[str, Any], int | None, list[str], dict[str, Any] | None]:
    cost_est = estimate_artifact_cost(kind=kind, n_media=n_media, resubmit=resubmit)
    est = int(cost_est.get("estimated_tokens") or 0)
    notes: list[str] = []
    effective = budget_remaining
    if effective is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(estimate_tokens=est)
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective = int(rem)
                notes.append(
                    f"budget hydrated: remaining_tokens={effective} "
                    f"pressure={snap.get('budget_pressure')}"
                )
        except Exception as exc:
            notes.append(f"budget hydrate skipped: {exc}")
    if effective is not None and est > int(effective):
        return (
            cost_est,
            effective,
            notes,
            {
                "ok": False,
                "blocked": True,
                "reason": "budget",
                "error": f"budget: est {est} tokens exceeds remaining {effective}",
                "cost_estimate_tokens": est,
                "budget_remaining": int(effective),
                "cost_estimate": cost_est,
                "notes": notes,
            },
        )
    return cost_est, effective, notes, None


def propose_artifact(
    kind: str,
    title: str,
    summary: str,
    *,
    content_path: str = "",
    content_excerpt: str = "",
    related_issue: int | None = None,
    related_epic: int | None = None,
    originating_question: int | None = None,
    media_links: list[str] | None = None,
    actor: str = "agent",
    base_dir: Path | None = None,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Create a pending Design or Research approval proposal.

    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    """
    k = "research" if (kind or "").lower().startswith("res") else "design"
    media = list(media_links or [])
    cost_est, effective_remaining, budget_notes, blocked = _artifact_budget_gate(
        kind=k,
        n_media=len(media),
        resubmit=False,
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
    if blocked is not None:
        return blocked
    ts = _now()
    pid = f"art-{uuid.uuid4().hex[:12]}"
    rec = ArtifactProposal(
        id=pid,
        kind=k,
        title=(title or f"{k.title()} artifact").strip(),
        summary=(summary or "").strip() or "No summary provided",
        content_path=content_path or "",
        content_excerpt=(content_excerpt or "")[:2000],
        related_issue=related_issue,
        related_epic=related_epic,
        originating_question=originating_question,
        media_links=media,
        status="pending",
        version=1,
        created_at=ts,
        updated_at=ts,
        actor=actor,
    )
    path = _path(pid, base_dir)
    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["ok"] = True
    out["path"] = str(path)
    out["marker"] = render_approval_marker(rec)
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    out["cost_estimate_tokens"] = est_tokens
    out["budget_remaining"] = effective_remaining
    out["cost_estimate"] = cost_est
    out["notes"] = list(budget_notes)
    out["prompt_segment"] = (
        f"Present {k} artifact '{rec.title}' for approval via ask_user_question. "
        f"Options: Approve | Revise (comment) | Reject. Summary: {rec.summary[:200]}. "
        f"Links: {content_path or 'n/a'}. Do not treat as authoritative until approved."
    )
    out["approval_prompt"] = (
        f"Approve this {k}? (#{related_issue or 'n/a'}) — Approve / Revise / Reject"
    )
    out["ask_user_question"] = ask_user_question_payload(out)
    try:
        from .autonomy import apply_live_budget_charge

        apply_live_budget_charge(
            out,
            tokens=est_tokens,
            use_live_budget=use_live_budget,
            action_kind="artifact_propose",
            reason=f"propose_artifact:{pid}",
        )
    except Exception:
        pass
    return out


def get_proposal(proposal_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = _path(proposal_id, base_dir)
    if not path.exists():
        matches = sorted(_ensure(base_dir).glob(f"{proposal_id}*.json"))
        if not matches:
            return None
        path = matches[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except Exception:
        return None


def list_proposals(
    *,
    status: str | None = "pending",
    kind: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for f in sorted(_ensure(base_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        # skip authoritative pointer files and history
        name = f.name
        if name.startswith("approved-") or name.endswith(".history.jsonl"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data.get("id"):
            continue
        if status and status != "all":
            if status == "actionable":
                if data.get("status") not in ACTIONABLE_STATUSES:
                    continue
            elif data.get("status") != status:
                continue
        if kind and data.get("kind") != kind.lower():
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def list_actionable_proposals(
    *,
    kind: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Pending + revised proposals that still need human feed action (#632)."""
    return list_proposals(status="actionable", kind=kind, limit=limit, base_dir=base_dir)


def get_proposal_history(
    proposal_id: str,
    *,
    base_dir: Path | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read decision history sidecar for a proposal."""
    data = get_proposal(proposal_id, base_dir=base_dir)
    if not data:
        return []
    hist_path = Path(data["path"]).with_suffix(".history.jsonl")
    if not hist_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in hist_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-max(1, int(limit)) :]


def resubmit_proposal(
    proposal_id: str,
    *,
    summary: str | None = None,
    content_path: str | None = None,
    content_excerpt: str | None = None,
    media_links: list[str] | None = None,
    title: str | None = None,
    actor: str = "agent",
    base_dir: Path | None = None,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Update a revised/pending artifact and re-open for approval (#632).

    Bumps version, sets status=pending, appends history event 'resubmitted'.
    #634: hydrate remaining from durable budget when use_live_budget; block if est exceeds remaining.
    """
    data = get_proposal(proposal_id, base_dir=base_dir)
    if not data:
        return {"ok": False, "error": f"not found: {proposal_id}"}
    rec = ArtifactProposal.from_dict(data)
    if rec.status not in ACTIONABLE_STATUSES and rec.status != "rejected":
        if rec.status == "approved":
            return {
                "ok": False,
                "error": "approved artifact is authoritative; propose a new version as a new proposal",
                "proposal": rec.to_dict(),
            }
    media = list(media_links) if media_links is not None else list(rec.media_links or [])
    cost_est, effective_remaining, budget_notes, blocked = _artifact_budget_gate(
        kind=str(rec.kind or "design"),
        n_media=len(media),
        resubmit=True,
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
    if blocked is not None:
        blocked["proposal_id"] = rec.id
        return blocked
    path = Path(data["path"])
    if title is not None:
        rec.title = title.strip() or rec.title
    if summary is not None:
        rec.summary = summary.strip() or rec.summary
    if content_path is not None:
        rec.content_path = content_path
    if content_excerpt is not None:
        rec.content_excerpt = content_excerpt[:2000]
    if media_links is not None:
        rec.media_links = list(media_links)
    rec.version = int(rec.version or 1) + 1
    rec.status = "pending"
    rec.actor = actor or rec.actor
    rec.updated_at = _now()
    rec.decision_note = ""
    rec.decided_by = None
    hist_path = path.with_suffix(".history.jsonl")
    with hist_path.open("a", encoding="utf-8") as hf:
        hf.write(
            json.dumps(
                {
                    "id": rec.id,
                    "decision": "resubmitted",
                    "by": actor,
                    "note": "content updated; re-opened for approval",
                    "version": rec.version,
                    "at": rec.updated_at,
                }
            )
            + "\n"
        )
    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["ok"] = True
    out["path"] = str(path)
    out["marker"] = render_approval_marker(rec)
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    out["cost_estimate_tokens"] = est_tokens
    out["budget_remaining"] = effective_remaining
    out["cost_estimate"] = cost_est
    out["notes"] = list(budget_notes)
    out["ask_user_question"] = ask_user_question_payload(out)
    out["prompt_segment"] = (
        f"Resubmitted {rec.kind} v{rec.version} '{rec.title}' for approval via ask_user_question."
    )
    try:
        from .autonomy import apply_live_budget_charge

        apply_live_budget_charge(
            out,
            tokens=est_tokens,
            use_live_budget=use_live_budget,
            action_kind="artifact_resubmit",
            reason=f"resubmit_proposal:{rec.id}",
        )
    except Exception:
        pass
    return out


def decide_proposal(
    proposal_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str = "",
    base_dir: Path | None = None,
    open_checkpoint: bool = False,
) -> dict[str, Any]:
    """Record approve|revise|reject; approved bumps version authority."""
    data = get_proposal(proposal_id, base_dir=base_dir)
    if not data:
        return {"ok": False, "error": f"not found: {proposal_id}"}
    path = Path(data["path"])
    rec = ArtifactProposal.from_dict(data)
    if rec.status not in ("pending", "revised"):
        # allow re-decide only from pending/revised
        if rec.status == "approved" and decision.lower() in ("revise", "reject"):
            pass  # allow superseding
        elif rec.status not in ("pending", "revised"):
            return {"ok": False, "error": f"already decided: {rec.status}", "proposal": rec.to_dict()}

    dec = (decision or "").lower().strip()
    mapping = {
        "approve": "approved",
        "approved": "approved",
        "revise": "revised",
        "reject": "rejected",
        "rejected": "rejected",
    }
    if dec not in mapping:
        return {"ok": False, "error": "decision must be approve|revise|reject"}

    new_status = mapping[dec]
    if new_status == "approved":
        rec.version = int(rec.version or 1)
    elif new_status == "revised":
        rec.version = int(rec.version or 1) + 1
        # remains actionable in feed until resubmit + re-approve
        rec.status = "revised"
    rec.status = new_status if new_status != "revised" else "revised"
    rec.decided_by = decided_by
    rec.decision_note = note or ""
    rec.updated_at = _now()

    # Write decision history sidecar
    hist_path = path.with_suffix(".history.jsonl")
    with hist_path.open("a", encoding="utf-8") as hf:
        hf.write(
            json.dumps(
                {
                    "id": rec.id,
                    "decision": new_status,
                    "by": decided_by,
                    "note": note,
                    "version": rec.version,
                    "at": rec.updated_at,
                }
            )
            + "\n"
        )

    # On approve, write authoritative pointer
    if new_status == "approved":
        auth = _ensure(base_dir) / f"approved-{rec.kind}-{rec.id}.json"
        auth.write_text(
            json.dumps(
                {
                    "proposal_id": rec.id,
                    "kind": rec.kind,
                    "title": rec.title,
                    "version": rec.version,
                    "content_path": rec.content_path,
                    "related_issue": rec.related_issue,
                    "approved_at": rec.updated_at,
                    "approved_by": decided_by,
                    "authoritative": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["ok"] = True
    out["path"] = str(path)
    out["marker"] = render_approval_marker(rec)
    out["next_prompt"] = {
        "approved": "Artifact is authoritative for planning; link from Feature/Epic and proceed.",
        "revised": (
            "Update artifact content then plate_artifact_resubmit "
            f"{rec.id} (or resubmit_proposal); stays in feed as revised until re-approved."
        ),
        "rejected": "Do not use this artifact; capture alternative via Research/Design issue.",
    }.get(new_status, "")
    out["history"] = get_proposal_history(rec.id, base_dir=base_dir, limit=10)
    # Optional #648 checkpoint when revise needs explicit follow-through
    if open_checkpoint and new_status == "revised" and rec.related_issue:
        try:
            from .checkpoint import create_checkpoint

            cp = create_checkpoint(
                title=f"Revise {rec.kind}: {rec.title}",
                reason=note or f"Artifact {rec.id} needs revision before use",
                impact="medium",
                action_kind="artifact_revise",
                related_issue=rec.related_issue,
                scope={"proposal_id": rec.id, "version": rec.version},
                created_by=decided_by,
            )
            out["checkpoint_id"] = cp.get("id")
            out["checkpoint"] = {"id": cp.get("id"), "status": cp.get("status")}
        except Exception:
            pass
    # #647: durable provenance for artifact decisions
    try:
        from .ledger import record_decision

        led = record_decision(
            action_kind=f"artifact_{rec.kind}",
            decision=new_status,
            reason=note or out["next_prompt"] or f"{new_status} {rec.kind} artifact",
            sources=["design_research_approval", "#632"],
            related_issue=rec.related_issue,
            actor=decided_by,
            checkpoint_id=out.get("checkpoint_id"),
            metadata={"proposal_id": rec.id, "version": rec.version, "title": rec.title},
            base_dir=None,
        )
        out["ledger_id"] = led.get("id")
    except Exception:
        pass
    return out


def list_authoritative(*, kind: str | None = None, base_dir: Path | None = None) -> list[dict[str, Any]]:
    d = _ensure(base_dir)
    rows = []
    for f in sorted(d.glob("approved-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if kind and data.get("kind") != kind.lower():
            continue
        data["path"] = str(f)
        rows.append(data)
    return rows


def render_approval_marker(rec: ArtifactProposal | dict[str, Any]) -> str:
    d = rec.to_dict() if isinstance(rec, ArtifactProposal) else dict(rec)
    payload = {
        "id": d.get("id"),
        "kind": d.get("kind"),
        "title": d.get("title"),
        "status": d.get("status"),
        "version": d.get("version"),
        "related_issue": d.get("related_issue"),
        "originating_question": d.get("originating_question"),
        "content_path": d.get("content_path"),
    }
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}"


def ask_user_question_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    """Native TUI payload for one Design/Research approval (#632)."""
    pid = str(proposal.get("id") or "artifact")
    kind = str(proposal.get("kind") or "design")
    title = str(proposal.get("title") or "artifact")
    summary = str(proposal.get("summary") or "")[:240]
    path = str(proposal.get("content_path") or "n/a")
    return {
        "item_id": pid,
        "item_type": "artifact_approval",
        "kind": kind,
        "question": (
            f"Approve {kind} artifact '{title}'?\n"
            f"Summary: {summary or '(none)'}\n"
            f"Path/link: {path}\n"
            "Not authoritative until Approve."
        ),
        "options": [
            {
                "id": "approve",
                "label": "Approve",
                "description": f"plate_artifact_decide {pid} approve — becomes authoritative.",
            },
            {
                "id": "revise",
                "label": "Revise",
                "description": f"plate_artifact_decide {pid} revise — bump version; re-propose content.",
            },
            {
                "id": "reject",
                "label": "Reject",
                "description": f"plate_artifact_decide {pid} reject — do not use.",
            },
            {
                "id": "open_artifact",
                "label": "Open artifact",
                "description": f"Review content at {path} before deciding.",
            },
        ],
        "multi_select": False,
        "related_issue": proposal.get("related_issue"),
        "originating_question": proposal.get("originating_question"),
        "media_links": list(proposal.get("media_links") or []),
    }


def presentation_for_feed(proposal: dict[str, Any]) -> dict[str, Any]:
    """Shape for #631 feed / ask_user_question."""
    payload = ask_user_question_payload(proposal)
    status = str(proposal.get("status") or "pending")
    reason = (
        "Design/Research revised — resubmit then re-approve (#632)"
        if status == "revised"
        else "Design/Research pending human approval (#632)"
    )
    # For revised items, prioritize resubmit path in options order via prompt
    if status == "revised":
        payload = dict(payload)
        payload["options"] = [
            {
                "id": "resubmit",
                "label": "Resubmit updated content",
                "description": (
                    f"plate_artifact_resubmit {proposal.get('id')} "
                    "after updating content_path/summary"
                ),
            },
            *list(payload.get("options") or []),
        ]
        payload["question"] = (
            f"Revised {proposal.get('kind')} '{proposal.get('title')}' "
            f"(v{proposal.get('version')}) — resubmit or re-decide?\n"
            f"Note: {proposal.get('decision_note') or '(none)'}"
        )
    return {
        "id": proposal.get("id"),
        "item_type": "artifact_approval",
        "kind": proposal.get("kind"),
        "title": proposal.get("title"),
        "status": status,
        "version": proposal.get("version"),
        "impact": "high",
        "rank": 11 if status == "revised" else 12,
        "prompt_segment": proposal.get("prompt_segment")
        or (
            f"Approve {proposal.get('kind')} '{proposal.get('title')}'? "
            "Approve / Revise / Reject"
        ),
        "url": proposal.get("content_path"),
        "ask_user_question": payload,
        "approval_prompt": proposal.get("approval_prompt") or payload.get("question"),
        "reason": reason,
    }


def artifact_feed_items(
    *,
    limit: int = 15,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Actionable Design/Research proposals for the endless feed (#632)."""
    items = []
    for prop in list_actionable_proposals(limit=limit, base_dir=base_dir):
        shaped = presentation_for_feed(prop)
        items.append(shaped)
    items.sort(key=lambda x: (int(x.get("rank") or 99), str(x.get("title") or "")))
    return items
