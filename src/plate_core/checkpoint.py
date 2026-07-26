"""Unified checkpoint / approval primitive (#648).

Single surface for requesting and recording human judgment across CLI, MCP,
and AutonomyEngine. Durable ledger lives under `.agentic/checkpoints/` (GitHub
is still the preferred audit trail when a Task issue is linked).

Design goals (v1 slice):
- create_checkpoint: structured pending approval with reason, impact, scope
- decide_checkpoint: approve | revise | reject with actor + note
- list_open_checkpoints / get_checkpoint
- policy auto-approval for low-impact at medium+ risk_tolerance
- HTML markers for GitHub-visible comments (PLATE-CHECKPOINT)
- Integrates with #645 shadow_id as optional scope field

Follow-ups: full TUI ask_user_question host bridge, Projects fields, pause of
whole AutonomyEngine loop via open checkpoints.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

CHECKPOINT_DIR = Path(".agentic/checkpoints")
MARKER_BEGIN = "<!-- PLATE-CHECKPOINT:BEGIN -->"
MARKER_END = "<!-- PLATE-CHECKPOINT:END -->"
DECISION_MARKER = "<!-- PLATE-CHECKPOINT-DECISION"


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REVISED = "revised"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    CANCELLED = "cancelled"


class CheckpointDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"
    CANCEL = "cancel"


@dataclass
class CheckpointRecord:
    """One human-judgment request."""

    id: str
    title: str
    reason: str
    status: str = CheckpointStatus.PENDING.value
    impact: str = "medium"  # low | medium | high | critical
    action_kind: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    shadow_id: str | None = None
    related_issue: int | None = None
    related_pr: int | None = None
    created_at: str = ""
    updated_at: str = ""
    created_by: str = "agent"
    decided_by: str | None = None
    decision_note: str | None = None
    auto_approved: bool = False
    pause_autonomy: bool = True  # pending checkpoints pause unsupervised cycles
    resume_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(base: Path | None = None) -> Path:
    d = (base or CHECKPOINT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path_for(checkpoint_id: str, base: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", checkpoint_id)
    return _ensure_dir(base) / f"{safe}.json"


def _impact_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get((level or "").lower(), 1)


def _risk_rank(tol: str) -> int:
    return {"off": 0, "low": 1, "medium": 2, "high": 3}.get((tol or "").lower(), 0)


def should_auto_approve(
    impact: str,
    risk_tolerance: str,
    *,
    enabled: bool = True,
) -> bool:
    """Policy: auto-approve only low impact when autonomy on and risk >= medium.

    Critical/high never auto-approve. Off/low risk never auto-approve.
    """
    if not enabled or (risk_tolerance or "off").lower() in ("off", "low", ""):
        return False
    if _impact_rank(impact) >= _impact_rank("high"):
        return False
    if _impact_rank(impact) == _impact_rank("low") and _risk_rank(risk_tolerance) >= _risk_rank("medium"):
        return True
    return False


def create_checkpoint(
    title: str,
    reason: str,
    *,
    impact: str = "medium",
    action_kind: str = "",
    scope: dict[str, Any] | None = None,
    shadow_id: str | None = None,
    related_issue: int | None = None,
    related_pr: int | None = None,
    created_by: str = "agent",
    risk_tolerance: str = "off",
    autonomy_enabled: bool = False,
    pause_autonomy: bool | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a pending (or auto-approved) checkpoint record."""
    scope = dict(scope or {})
    if shadow_id:
        scope.setdefault("shadow_id", shadow_id)
    ts = _now()
    cid = f"cp-{uuid.uuid4().hex[:12]}"
    impact_n = (impact or "medium").lower()
    auto = should_auto_approve(impact_n, risk_tolerance, enabled=autonomy_enabled)
    status = CheckpointStatus.AUTO_APPROVED.value if auto else CheckpointStatus.PENDING.value
    # high/critical always pause; low auto-approved does not
    if pause_autonomy is None:
        pause_autonomy = (not auto) and _impact_rank(impact_n) >= _impact_rank("medium")

    rec = CheckpointRecord(
        id=cid,
        title=(title or "Human checkpoint").strip(),
        reason=(reason or "").strip() or "Human judgment required",
        status=status,
        impact=impact_n,
        action_kind=(action_kind or "").lower().replace("-", "_"),
        scope=scope,
        shadow_id=shadow_id or scope.get("shadow_id"),
        related_issue=related_issue,
        related_pr=related_pr,
        created_at=ts,
        updated_at=ts,
        created_by=created_by,
        decided_by="policy" if auto else None,
        decision_note="auto-approved by risk policy (low impact, risk_tolerance>=medium)" if auto else None,
        auto_approved=auto,
        pause_autonomy=bool(pause_autonomy) and not auto,
        resume_hint=(
            f"gh plate checkpoint decide {cid} --decision approve"
            if not auto
            else "auto-approved; resume without human"
        ),
    )
    path = _path_for(cid, base_dir)
    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["marker"] = render_checkpoint_marker(rec)
    out["path"] = str(path)
    return out


def get_checkpoint(checkpoint_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = _path_for(checkpoint_id, base_dir)
    if not path.exists():
        # allow prefix match
        d = _ensure_dir(base_dir)
        matches = sorted(d.glob(f"{checkpoint_id}*.json"))
        if not matches:
            return None
        path = matches[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except Exception:
        return None


def list_checkpoints(
    *,
    status: str | None = "pending",
    base_dir: Path | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    d = _ensure_dir(base_dir)
    rows: list[dict[str, Any]] = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and status != "all" and data.get("status") != status:
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def list_open_checkpoints(*, base_dir: Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Pending checkpoints that should pause unsupervised autonomy."""
    return [
        c
        for c in list_checkpoints(status="pending", base_dir=base_dir, limit=limit)
        if c.get("pause_autonomy", True)
    ]


def decide_checkpoint(
    checkpoint_id: str,
    decision: str,
    *,
    decided_by: str = "human",
    note: str = "",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Record approve|revise|reject|cancel on an existing checkpoint."""
    rec_dict = get_checkpoint(checkpoint_id, base_dir=base_dir)
    if not rec_dict:
        return {"ok": False, "error": f"checkpoint not found: {checkpoint_id}"}
    path = Path(rec_dict["path"])
    rec = CheckpointRecord.from_dict(rec_dict)

    if rec.status not in (CheckpointStatus.PENDING.value,):
        return {
            "ok": False,
            "error": f"checkpoint already decided: status={rec.status}",
            "checkpoint": rec.to_dict(),
        }

    dec = (decision or "").lower().strip()
    mapping = {
        "approve": CheckpointStatus.APPROVED.value,
        "approved": CheckpointStatus.APPROVED.value,
        "revise": CheckpointStatus.REVISED.value,
        "reject": CheckpointStatus.REJECTED.value,
        "rejected": CheckpointStatus.REJECTED.value,
        "cancel": CheckpointStatus.CANCELLED.value,
        "cancelled": CheckpointStatus.CANCELLED.value,
    }
    if dec not in mapping:
        return {
            "ok": False,
            "error": f"invalid decision '{decision}'; use approve|revise|reject|cancel",
        }

    rec.status = mapping[dec]
    rec.decided_by = decided_by
    rec.decision_note = note or None
    rec.updated_at = _now()
    rec.pause_autonomy = False
    if rec.status == CheckpointStatus.APPROVED.value:
        rec.resume_hint = f"approved; proceed with action_kind={rec.action_kind or 'n/a'}"
    elif rec.status == CheckpointStatus.REVISED.value:
        rec.resume_hint = "revise requested; update plan then create a new checkpoint"
    else:
        rec.resume_hint = f"status={rec.status}; do not proceed with the gated action"

    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["ok"] = True
    out["path"] = str(path)
    out["decision_marker"] = (
        f"{DECISION_MARKER} id={rec.id} decision={dec} by={decided_by} -->"
    )
    out["marker"] = render_checkpoint_marker(rec)
    return out


def render_checkpoint_marker(rec: CheckpointRecord | dict[str, Any]) -> str:
    """GitHub-safe marker block for issue/PR comments."""
    d = rec.to_dict() if isinstance(rec, CheckpointRecord) else dict(rec)
    payload = {
        "id": d.get("id"),
        "title": d.get("title"),
        "status": d.get("status"),
        "impact": d.get("impact"),
        "action_kind": d.get("action_kind"),
        "shadow_id": d.get("shadow_id"),
        "related_issue": d.get("related_issue"),
        "related_pr": d.get("related_pr"),
        "pause_autonomy": d.get("pause_autonomy"),
        "resume_hint": d.get("resume_hint"),
    }
    body = json.dumps(payload, indent=2)
    return f"{MARKER_BEGIN}\n{body}\n{MARKER_END}"


def autonomy_is_paused_by_checkpoints(*, base_dir: Path | None = None) -> dict[str, Any]:
    """Whether open pausing checkpoints should block unsupervised cycles."""
    open_cps = list_open_checkpoints(base_dir=base_dir)
    return {
        "paused": len(open_cps) > 0,
        "open_count": len(open_cps),
        "checkpoint_ids": [c.get("id") for c in open_cps],
        "titles": [c.get("title") for c in open_cps],
    }


def checkpoint_approval_for_gate(
    checkpoint_id: str,
    *,
    action_kind: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Resolve a decided checkpoint for #645 gate_high_impact (#648 bridge).

    Returns {ok, approved, shadow_id, action_kind, checkpoint?, reason?}.
    approved=True only when status is approved|auto_approved and (optional)
    action_kind matches when both sides provide one.
    """
    rec = get_checkpoint(checkpoint_id, base_dir=base_dir)
    if not rec:
        return {
            "ok": False,
            "approved": False,
            "shadow_id": None,
            "action_kind": None,
            "reason": f"checkpoint not found: {checkpoint_id}",
        }
    status = str(rec.get("status") or "").lower()
    approved_statuses = {
        CheckpointStatus.APPROVED.value,
        CheckpointStatus.AUTO_APPROVED.value,
    }
    if status not in approved_statuses:
        return {
            "ok": True,
            "approved": False,
            "shadow_id": rec.get("shadow_id"),
            "action_kind": rec.get("action_kind"),
            "checkpoint": rec,
            "reason": f"checkpoint status={status} (need approved)",
        }
    cp_kind = (rec.get("action_kind") or "").lower().replace("-", "_")
    want = (action_kind or "").lower().replace("-", "_")
    if want and cp_kind and want != cp_kind:
        # Allow run_procedure / deploy aliases when critical gate uses deploy
        aliases = {
            "run_procedure": {"run_procedure", "deploy"},
            "deploy": {"deploy", "run_procedure", "release_cut", "release_finalize"},
        }
        allowed = aliases.get(want, {want})
        if cp_kind not in allowed and want not in aliases.get(cp_kind, {cp_kind}):
            return {
                "ok": True,
                "approved": False,
                "shadow_id": rec.get("shadow_id"),
                "action_kind": rec.get("action_kind"),
                "checkpoint": rec,
                "reason": f"checkpoint action_kind={cp_kind} does not match gate {want}",
            }
    return {
        "ok": True,
        "approved": True,
        "shadow_id": rec.get("shadow_id"),
        "action_kind": rec.get("action_kind"),
        "checkpoint": rec,
        "reason": rec.get("resume_hint") or "checkpoint approved",
    }


def find_open_checkpoint(
    *,
    action_kind: str | None = None,
    shadow_id: str | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return a pending open checkpoint matching action_kind and/or shadow_id.

    Used to dedupe #645/#648 gate spam: repeated gate_high_impact calls for the
    same action must not create a new pause_autonomy checkpoint each time.
    Prefer exact shadow_id match; else same action_kind with pause_autonomy.
    """
    action_n = (action_kind or "").lower().replace("-", "_").strip()
    sid = (shadow_id or "").strip() or None
    if not action_n and not sid:
        return None
    try:
        open_cps = list_open_checkpoints(base_dir=base_dir, limit=100)
    except Exception:
        return None
    # 1) exact shadow_id
    if sid:
        for cp in open_cps:
            if str(cp.get("shadow_id") or "") == sid:
                return cp
    # 2) same action_kind (pending pause gates only)
    if action_n:
        for cp in open_cps:
            if str(cp.get("action_kind") or "").lower().replace("-", "_") == action_n:
                if cp.get("pause_autonomy", True):
                    return cp
    return None


def create_checkpoint_for_shadow(
    shadow_report: dict[str, Any],
    *,
    title: str | None = None,
    risk_tolerance: str = "off",
    autonomy_enabled: bool = False,
    created_by: str = "agent",
    base_dir: Path | None = None,
    dedupe: bool = True,
) -> dict[str, Any]:
    """Bridge #645 ShadowReport → #648 checkpoint when approval required.

    When ``dedupe`` is True (default), reuses an open pending checkpoint for the
    same action_kind/shadow_id instead of opening another pause gate.
    """
    impact = (shadow_report or {}).get("impact") or "high"
    action = (shadow_report or {}).get("action_kind") or "unknown"
    reasons = (shadow_report or {}).get("approval_reasons") or []
    reason = "; ".join(reasons) if reasons else f"Shadow preview requires approval for {action}"
    sid = shadow_report.get("shadow_id")
    if dedupe:
        existing = find_open_checkpoint(
            action_kind=str(action),
            shadow_id=str(sid) if sid else None,
            base_dir=base_dir,
        )
        if existing:
            out = dict(existing)
            out["deduped"] = True
            # Refresh shadow_id on the open record when a newer preview arrives
            if sid and not out.get("shadow_id"):
                try:
                    path = Path(str(out.get("path") or _path_for(str(out["id"]), base_dir)))
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["shadow_id"] = sid
                    data["updated_at"] = _now()
                    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                    out = data
                    out["path"] = str(path)
                    out["deduped"] = True
                except Exception:
                    pass
            return out
    return create_checkpoint(
        title=title or f"Approve {action} ({impact})",
        reason=reason,
        impact=impact,
        action_kind=action,
        scope={
            "estimated_tokens": shadow_report.get("estimated_tokens"),
            "estimated_cost_usd": shadow_report.get("estimated_cost_usd"),
            "predicted_side_effects": shadow_report.get("predicted_side_effects"),
            "gate_preview": shadow_report.get("gate_preview"),
        },
        shadow_id=sid,
        created_by=created_by,
        risk_tolerance=risk_tolerance,
        autonomy_enabled=autonomy_enabled,
        base_dir=base_dir,
    )
