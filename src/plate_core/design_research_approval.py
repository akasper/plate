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
) -> dict[str, Any]:
    """Create a pending Design or Research approval proposal."""
    k = "research" if (kind or "").lower().startswith("res") else "design"
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
        media_links=list(media_links or []),
        status="pending",
        version=1,
        created_at=ts,
        updated_at=ts,
        actor=actor,
    )
    path = _path(pid, base_dir)
    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["path"] = str(path)
    out["marker"] = render_approval_marker(rec)
    out["prompt_segment"] = (
        f"Present {k} artifact '{rec.title}' for approval via ask_user_question. "
        f"Options: Approve | Revise (comment) | Reject. Summary: {rec.summary[:200]}. "
        f"Links: {content_path or 'n/a'}. Do not treat as authoritative until approved."
    )
    out["approval_prompt"] = (
        f"Approve this {k}? (#{related_issue or 'n/a'}) — Approve / Revise / Reject"
    )
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
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and status != "all" and data.get("status") != status:
            continue
        if kind and data.get("kind") != kind.lower():
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def decide_proposal(
    proposal_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str = "",
    base_dir: Path | None = None,
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
        # back to pending-like workflow for next cycle
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
        "revised": "Revise artifact content, then propose_artifact again or re-submit same id after update.",
        "rejected": "Do not use this artifact; capture alternative via Research/Design issue.",
    }.get(new_status, "")
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


def presentation_for_feed(proposal: dict[str, Any]) -> dict[str, Any]:
    """Shape for #631 feed / ask_user_question."""
    return {
        "id": proposal.get("id"),
        "item_type": "artifact_approval",
        "kind": proposal.get("kind"),
        "title": proposal.get("title"),
        "status": proposal.get("status"),
        "impact": "high",
        "prompt_segment": proposal.get("prompt_segment")
        or (
            f"Approve {proposal.get('kind')} '{proposal.get('title')}'? "
            "Approve / Revise / Reject"
        ),
        "url": proposal.get("content_path"),
        "reason": "Design/Research pending human approval (#632)",
    }
