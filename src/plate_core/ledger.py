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


# Decisions that should surface as human-attention feed gates (#647 harden)
BLOCKING_DECISIONS = frozenset(
    {"pause", "shadow_required", "reject", "rejected", "block", "blocked"}
)


def list_blocking_decisions(
    *,
    limit: int = 20,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Recent ledger rows that represent pause/shadow/reject gates."""
    out: list[dict[str, Any]] = []
    for row in list_decisions(limit=max(limit * 5, 50), base_dir=base_dir):
        if str(row.get("decision") or "").lower() in BLOCKING_DECISIONS:
            out.append(row)
        if len(out) >= limit:
            break
    return out


def ledger_summary(*, base_dir: Path | None = None, limit: int = 20) -> dict[str, Any]:
    """Compact summary for status/dashboard/feed consumers (#647)."""
    rows = list_decisions(limit=limit, base_dir=base_dir)
    by_decision: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_impact: dict[str, int] = {}
    blocking: list[dict[str, Any]] = []
    for r in rows:
        d = str(r.get("decision") or "unknown")
        by_decision[d] = by_decision.get(d, 0) + 1
        ak = str(r.get("action_kind") or "unknown")
        by_action[ak] = by_action.get(ak, 0) + 1
        imp = str(r.get("impact") or "unset") or "unset"
        by_impact[imp] = by_impact.get(imp, 0) + 1
        if d in BLOCKING_DECISIONS:
            blocking.append(
                {
                    "id": r.get("id"),
                    "action_kind": r.get("action_kind"),
                    "decision": r.get("decision"),
                    "reason": r.get("reason"),
                    "checkpoint_id": r.get("checkpoint_id"),
                    "shadow_id": r.get("shadow_id"),
                    "related_issue": r.get("related_issue"),
                    "created_at": r.get("created_at"),
                }
            )
    return {
        "count": len(rows),
        "by_decision": by_decision,
        "by_action_kind": by_action,
        "by_impact": by_impact,
        "blocking_count": len(blocking),
        "blocking": blocking[:10],
        "last_blocking": blocking[0] if blocking else None,
        "recent_ids": [r.get("id") for r in rows[:10]],
        "dir": str(_ensure_dir(base_dir)),
    }


def ledger_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Ranked feed signals from recent blocking ledger decisions (#647 → #631).

    Hosts present ask_user_question; agents should open checkpoint/shadow resume
    rather than re-running the gated action blindly.
    """
    items: list[dict[str, Any]] = []
    for i, row in enumerate(list_blocking_decisions(limit=limit, base_dir=base_dir)):
        eid = str(row.get("id") or f"dec-{i}")
        dec = str(row.get("decision") or "pause")
        kind = str(row.get("action_kind") or "unknown")
        reason = str(row.get("reason") or "")[:160]
        title = f"Ledger {dec}: {kind}"
        if row.get("related_issue"):
            title += f" (#{row['related_issue']})"
        impact = str(row.get("impact") or "").lower()
        if impact not in ("low", "medium", "high", "critical"):
            impact = "high" if dec in BLOCKING_DECISIONS else "medium"
        cp = row.get("checkpoint_id")
        sid = row.get("shadow_id")
        options = [
            {
                "id": "inspect",
                "label": "Inspect ledger entry",
                "description": f"gh plate ledger --get {eid} / plate_ledger_get",
            },
        ]
        if cp:
            options.append(
                {
                    "id": "decide_checkpoint",
                    "label": "Decide checkpoint",
                    "description": f"plate_checkpoint_decide {cp} approve|reject",
                }
            )
        if sid:
            options.append(
                {
                    "id": "resume_shadow",
                    "label": "Resume with shadow ack",
                    "description": f"gate_high_impact(..., shadow_ack={sid}, approved=True)",
                }
            )
        options.append(
            {
                "id": "ack",
                "label": "Acknowledge only",
                "description": "Leave gate in place; no action",
            }
        )
        steps = [
            f"plate_ledger_get id={eid}",
            f"decision={dec} action={kind}: {reason}",
        ]
        if cp:
            steps.append(f"checkpoint_id={cp}")
        if sid:
            steps.append(f"shadow_id={sid}")
        items.append(
            {
                "id": eid,
                "item_type": "ledger_gate",
                "type": "ledger_gate",
                "title": title,
                "rank": 12 + i,  # after hard checkpoints (~10), before general drift
                "impact": impact,
                "decision": dec,
                "action_kind": kind,
                "checkpoint_id": cp,
                "shadow_id": sid,
                "related_issue": row.get("related_issue"),
                "related_pr": row.get("related_pr"),
                "reason": reason or f"Autonomous decision {dec} for {kind}",
                "prompt_segment": (
                    f"{title}. {reason} "
                    f"Do not re-run gated action without checkpoint/shadow approval."
                ),
                "source": "decision_ledger",
                "badges": ["ledger", dec, impact],
                "marker": row.get("marker") or render_decision_marker(row),
                "ask_user_question": {
                    "question": f"{title} — next step?",
                    "options": options,
                },
                "steps": steps,
            }
        )
    return items


def format_ledger_summary_markdown(summary: dict[str, Any] | None = None, *, base_dir: Path | None = None) -> str:
    """CLI/wiki-friendly ledger summary (#647)."""
    s = summary if summary is not None else ledger_summary(base_dir=base_dir)
    lines = [
        "# Decision ledger summary",
        "",
        f"- Entries (window): {s.get('count')}",
        f"- Blocking: {s.get('blocking_count')}",
        f"- By decision: {s.get('by_decision')}",
        f"- By action: {s.get('by_action_kind')}",
        f"- Dir: {s.get('dir')}",
        "",
    ]
    blocking = s.get("blocking") or []
    if blocking:
        lines.append("## Blocking (recent)")
        lines.append("")
        for b in blocking[:8]:
            lines.append(
                f"- `{b.get('id')}` {b.get('decision')} {b.get('action_kind')}: "
                f"{str(b.get('reason') or '')[:100]}"
            )
        lines.append("")
    return "\n".join(lines)
