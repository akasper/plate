"""Provenance + decision ledger for autonomous actions (#647).

Every autonomous decision/action can append an inspectable, queryable record:
- Why the action was chosen or skipped
- Data sources (health, Goals, Q&A, SPEC, shadow/checkpoint ids)
- Cost/risk reasoning
- Structured PLATE-DECISION markers for GitHub comments

Durable store: `.agentic/ledger/<id>.json` (append-only files).
Complements USAGE REPORTs and PLATE-AUTONOMY-CYCLE markers without replacing them.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_DIR = Path(".agentic/ledger")
MARKER_BEGIN = "<!-- PLATE-DECISION:BEGIN -->"
MARKER_END = "<!-- PLATE-DECISION:END -->"


@dataclass
class DecisionRecord:
    """One inspectable autonomous decision/action."""

    id: str
    action_kind: str
    decision: str  # proceed | throttle | pause | warn | skip | approve | reject | delegate | shadow_required
    reason: str
    sources: list[str] = field(default_factory=list)
    cost_estimate_tokens: int | None = None
    risk_tolerance: str = ""
    impact: str = ""
    related_issue: int | None = None
    related_pr: int | None = None
    shadow_id: str | None = None
    checkpoint_id: str | None = None
    artifact_links: list[str] = field(default_factory=list)
    actor: str = "autonomy"
    session: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(base: Path | None = None) -> Path:
    d = base or LEDGER_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path_for(entry_id: str, base: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", entry_id)
    return _ensure_dir(base) / f"{safe}.json"


def record_decision(
    action_kind: str,
    decision: str,
    reason: str,
    *,
    sources: list[str] | None = None,
    cost_estimate_tokens: int | None = None,
    risk_tolerance: str = "",
    impact: str = "",
    related_issue: int | None = None,
    related_pr: int | None = None,
    shadow_id: str | None = None,
    checkpoint_id: str | None = None,
    artifact_links: list[str] | None = None,
    actor: str = "autonomy",
    session: str = "",
    metadata: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Append a decision/provenance record to the durable ledger."""
    ts = _now()
    eid = f"dec-{uuid.uuid4().hex[:12]}"
    rec = DecisionRecord(
        id=eid,
        action_kind=(action_kind or "unknown").lower().replace("-", "_"),
        decision=(decision or "proceed").lower(),
        reason=(reason or "").strip() or "no reason provided",
        sources=list(sources or []),
        cost_estimate_tokens=cost_estimate_tokens,
        risk_tolerance=risk_tolerance or "",
        impact=(impact or "").lower(),
        related_issue=related_issue,
        related_pr=related_pr,
        shadow_id=shadow_id,
        checkpoint_id=checkpoint_id,
        artifact_links=list(artifact_links or []),
        actor=actor or "autonomy",
        session=session or "",
        metadata=dict(metadata or {}),
        created_at=ts,
    )
    path = _path_for(eid, base_dir)
    path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    out = rec.to_dict()
    out["path"] = str(path)
    out["marker"] = render_decision_marker(rec)
    return out


def get_decision(entry_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = _path_for(entry_id, base_dir)
    if not path.exists():
        d = _ensure_dir(base_dir)
        matches = sorted(d.glob(f"{entry_id}*.json"))
        if not matches:
            return None
        path = matches[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["path"] = str(path)
        return data
    except Exception:
        return None


def list_decisions(
    *,
    action_kind: str | None = None,
    decision: str | None = None,
    related_issue: int | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """List ledger entries newest-first with optional filters."""
    d = _ensure_dir(base_dir)
    rows: list[dict[str, Any]] = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if action_kind and data.get("action_kind") != action_kind.lower().replace("-", "_"):
            continue
        if decision and data.get("decision") != decision.lower():
            continue
        if related_issue is not None and data.get("related_issue") != related_issue:
            continue
        data["path"] = str(f)
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows


def query_decisions(
    query: str,
    *,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Simple substring search over reason, sources, action_kind, metadata JSON."""
    q = (query or "").strip().lower()
    if not q:
        return list_decisions(limit=limit, base_dir=base_dir)
    rows: list[dict[str, Any]] = []
    for item in list_decisions(limit=500, base_dir=base_dir):
        blob = " ".join(
            [
                str(item.get("action_kind") or ""),
                str(item.get("decision") or ""),
                str(item.get("reason") or ""),
                " ".join(item.get("sources") or []),
                str(item.get("shadow_id") or ""),
                str(item.get("checkpoint_id") or ""),
                json.dumps(item.get("metadata") or {}, sort_keys=True),
            ]
        ).lower()
        if q in blob:
            rows.append(item)
        if len(rows) >= limit:
            break
    return rows


def render_decision_marker(rec: DecisionRecord | dict[str, Any]) -> str:
    """GitHub-safe marker for issue/PR comments."""
    d = rec.to_dict() if isinstance(rec, DecisionRecord) else dict(rec)
    payload = {
        "id": d.get("id"),
        "action_kind": d.get("action_kind"),
        "decision": d.get("decision"),
        "reason": d.get("reason"),
        "sources": d.get("sources"),
        "cost_estimate_tokens": d.get("cost_estimate_tokens"),
        "risk_tolerance": d.get("risk_tolerance"),
        "impact": d.get("impact"),
        "shadow_id": d.get("shadow_id"),
        "checkpoint_id": d.get("checkpoint_id"),
        "related_issue": d.get("related_issue"),
        "related_pr": d.get("related_pr"),
        "created_at": d.get("created_at"),
    }
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}"


def record_from_autonomy_action(
    action: dict[str, Any],
    *,
    risk_tolerance: str = "",
    session: str = "",
    actor: str = "autonomy",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Helper: map AutonomyEngine action dict → ledger entry."""
    kind = str(action.get("type") or action.get("kind") or "unknown")
    decision = str(action.get("decision") or "proceed")
    reasons: list[str] = []
    if action.get("annotation"):
        reasons.append(str(action["annotation"]))
    if action.get("throttled"):
        reasons.append("throttled by budget governor")
    if action.get("id"):
        reasons.append(f"procedure_id={action['id']}")
    reason = "; ".join(reasons) if reasons else f"autonomy decided {decision} for {kind}"
    sources = ["autonomy_engine", "decide_next"]
    if action.get("id"):
        sources.append(f"procedure:{action['id']}")
    return record_decision(
        action_kind=kind,
        decision=decision,
        reason=reason,
        sources=sources,
        cost_estimate_tokens=action.get("est"),
        risk_tolerance=risk_tolerance,
        actor=actor,
        session=session,
        metadata={"raw_action": {k: action[k] for k in action if k != "prompt_segment"}},
        base_dir=base_dir,
    )


def ledger_summary(*, base_dir: Path | None = None, limit: int = 20) -> dict[str, Any]:
    """Compact summary for status/dashboard consumers."""
    rows = list_decisions(limit=limit, base_dir=base_dir)
    by_decision: dict[str, int] = {}
    for r in rows:
        d = str(r.get("decision") or "unknown")
        by_decision[d] = by_decision.get(d, 0) + 1
    return {
        "count": len(rows),
        "by_decision": by_decision,
        "recent_ids": [r.get("id") for r in rows[:10]],
        "dir": str(_ensure_dir(base_dir)),
    }
