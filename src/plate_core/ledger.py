"""Provenance + decision ledger for autonomous actions (#647).

Every autonomous decision/action can append an inspectable, queryable record:
- Why the action was chosen or skipped
- Data sources (health, Goals, Q&A, SPEC, shadow/checkpoint ids)
- Cost/risk reasoning
- Structured PLATE-DECISION markers for GitHub comments

Spend intervals (#1352) use the same durable store with record_type=spend_interval
for per-run token/cost attribution (pilot #1338 / lifecycle tasks beyond dev).

Optional Jev shadow fields on the same record type (#1356): parallel scores alongside
fixed-table routing; nothing in plate_core reads them for routing.

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

RECORD_TYPE_DECISION = "decision"
RECORD_TYPE_SPEND_INTERVAL = "spend_interval"
VALID_TIERS = frozenset({"T0", "T1", "T2", "T3"})
VALID_ROUTE_CLARITY = frozenset({"clear", "ambiguous"})
HANDOFF_PACKET_UNITS = frozenset({"tokens", "bytes"})


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


@dataclass
class SpendIntervalRecord:
    """One inspectable spend interval for a cloud agent run (#1352)."""

    id: str
    record_type: str = RECORD_TYPE_SPEND_INTERVAL
    cloud_agent_id: str | None = None
    parent_run_id: str | None = None
    run_id: str | None = None
    lifecycle_task_type: str = ""
    model: str | None = None
    tier: str | None = None
    effort: str | None = None
    hardware: str | None = None
    route_clarity: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    tool_output_tokens: int | None = None
    turns: int | None = None
    handoff_packet_size: int | None = None
    handoff_packet_unit: str | None = None
    rediscovery_count: int | None = None
    outcome_accepted: bool | None = None
    cost_usd: float | None = None
    jev_score: float | None = None
    jev_suggested_tier: str | None = None
    jev_model: str | None = None
    jev_route_clarity: str | None = None
    related_issue: int | None = None
    related_pr: int | None = None
    session: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpendIntervalRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def ledger_record_type(data: dict[str, Any]) -> str:
    rt = str(data.get("record_type") or RECORD_TYPE_DECISION).lower()
    if rt == RECORD_TYPE_SPEND_INTERVAL:
        return RECORD_TYPE_SPEND_INTERVAL
    return RECORD_TYPE_DECISION


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes", "accepted"):
            return True
        if low in ("false", "0", "no", "rejected"):
            return False
    return None


def validate_ledger_entry(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a ledger JSON object; return normalized dict or errors (#1352 extends #647)."""
    if not isinstance(data, dict):
        return None, ["entry must be a JSON object"]
    errors: list[str] = []
    rt = ledger_record_type(data)
    if rt == RECORD_TYPE_DECISION:
        if not str(data.get("id") or "").strip():
            errors.append("decision entries require id")
        if not str(data.get("action_kind") or "").strip():
            errors.append("decision entries require action_kind")
        if not str(data.get("decision") or "").strip():
            errors.append("decision entries require decision")
        if errors:
            return None, errors
        rec = DecisionRecord.from_dict(data)
        return rec.to_dict(), []
    if rt != RECORD_TYPE_SPEND_INTERVAL:
        return None, [f"unknown record_type: {data.get('record_type')!r}"]

    tier = data.get("tier")
    if tier is not None and str(tier).strip() and str(tier).upper() not in VALID_TIERS:
        errors.append(f"tier must be one of {sorted(VALID_TIERS)}")
    route = data.get("route_clarity")
    if route is not None and str(route).strip() and str(route).lower() not in VALID_ROUTE_CLARITY:
        errors.append(f"route_clarity must be one of {sorted(VALID_ROUTE_CLARITY)}")
    unit = data.get("handoff_packet_unit")
    if unit is not None and str(unit).strip() and str(unit).lower() not in HANDOFF_PACKET_UNITS:
        errors.append(f"handoff_packet_unit must be one of {sorted(HANDOFF_PACKET_UNITS)}")
    jev_tier = data.get("jev_suggested_tier")
    if jev_tier is not None and str(jev_tier).strip() and str(jev_tier).upper() not in VALID_TIERS:
        errors.append(f"jev_suggested_tier must be one of {sorted(VALID_TIERS)}")
    jev_route = data.get("jev_route_clarity")
    if (
        jev_route is not None
        and str(jev_route).strip()
        and str(jev_route).lower() not in VALID_ROUTE_CLARITY
    ):
        errors.append(f"jev_route_clarity must be one of {sorted(VALID_ROUTE_CLARITY)}")
    if not str(data.get("id") or "").strip():
        errors.append("spend_interval entries require id")
    if errors:
        return None, errors

    normalized = SpendIntervalRecord.from_dict(
        {
            **data,
            "record_type": RECORD_TYPE_SPEND_INTERVAL,
            "tier": str(tier).upper() if tier not in (None, "") else None,
            "route_clarity": str(route).lower() if route not in (None, "") else None,
            "handoff_packet_unit": str(unit).lower() if unit not in (None, "") else None,
            "input_tokens": _optional_int(data.get("input_tokens")),
            "output_tokens": _optional_int(data.get("output_tokens")),
            "cached_read_tokens": _optional_int(data.get("cached_read_tokens")),
            "cache_write_tokens": _optional_int(data.get("cache_write_tokens")),
            "tool_output_tokens": _optional_int(data.get("tool_output_tokens")),
            "turns": _optional_int(data.get("turns")),
            "handoff_packet_size": _optional_int(data.get("handoff_packet_size")),
            "rediscovery_count": _optional_int(data.get("rediscovery_count")),
            "related_issue": _optional_int(data.get("related_issue")),
            "related_pr": _optional_int(data.get("related_pr")),
            "cost_usd": _optional_float(data.get("cost_usd")),
            "outcome_accepted": _optional_bool(data.get("outcome_accepted")),
            "jev_score": _optional_float(data.get("jev_score")),
            "jev_suggested_tier": (
                str(jev_tier).upper() if jev_tier not in (None, "") else None
            ),
            "jev_route_clarity": (
                str(jev_route).lower() if jev_route not in (None, "") else None
            ),
        }
    ).to_dict()
    return normalized, []


def spend_interval_has_jev_score(entry: dict[str, Any]) -> bool:
    """True when a spend row carries a recorded Jev shadow score (#1356)."""
    return entry.get("jev_score") is not None


def sum_spend_interval_tokens(entry: dict[str, Any]) -> int | None:
    """Sum token fields present on a spend interval; None when no token fields were recorded."""
    keys = (
        "input_tokens",
        "output_tokens",
        "cached_read_tokens",
        "cache_write_tokens",
        "tool_output_tokens",
    )
    parts = [entry[k] for k in keys if entry.get(k) is not None]
    if not parts:
        return None
    return sum(int(v) for v in parts)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(base: Path | None = None) -> Path:
    d = base or LEDGER_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path_for(entry_id: str, base: Path | None = None) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", entry_id)
    return _ensure_dir(base) / f"{safe}.json"


def _read_ledger_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    normalized, errors = validate_ledger_entry(data)
    if errors:
        return data
    return normalized or data


def record_spend_interval(
    *,
    cloud_agent_id: str | None = None,
    parent_run_id: str | None = None,
    run_id: str | None = None,
    lifecycle_task_type: str = "",
    model: str | None = None,
    tier: str | None = None,
    effort: str | None = None,
    hardware: str | None = None,
    route_clarity: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    tool_output_tokens: int | None = None,
    turns: int | None = None,
    handoff_packet_size: int | None = None,
    handoff_packet_unit: str | None = None,
    rediscovery_count: int | None = None,
    outcome_accepted: bool | None = None,
    cost_usd: float | None = None,
    jev_score: float | None = None,
    jev_suggested_tier: str | None = None,
    jev_model: str | None = None,
    jev_route_clarity: str | None = None,
    related_issue: int | None = None,
    related_pr: int | None = None,
    session: str = "",
    metadata: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Append a spend interval row for run-level attribution (#1352)."""
    ts = _now()
    eid = f"spend-{uuid.uuid4().hex[:12]}"
    draft = {
        "id": eid,
        "record_type": RECORD_TYPE_SPEND_INTERVAL,
        "cloud_agent_id": (cloud_agent_id or None),
        "parent_run_id": (parent_run_id or None),
        "run_id": (run_id or None),
        "lifecycle_task_type": (lifecycle_task_type or "").strip(),
        "model": (model or None),
        "tier": (tier or None),
        "effort": (effort or None),
        "hardware": (hardware or None),
        "route_clarity": (route_clarity or None),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_read_tokens": cached_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "tool_output_tokens": tool_output_tokens,
        "turns": turns,
        "handoff_packet_size": handoff_packet_size,
        "handoff_packet_unit": (handoff_packet_unit or None),
        "rediscovery_count": rediscovery_count,
        "outcome_accepted": outcome_accepted,
        "cost_usd": cost_usd,
        "jev_score": jev_score,
        "jev_suggested_tier": (jev_suggested_tier or None),
        "jev_model": (jev_model or None),
        "jev_route_clarity": (jev_route_clarity or None),
        "related_issue": related_issue,
        "related_pr": related_pr,
        "session": session or "",
        "metadata": dict(metadata or {}),
        "created_at": ts,
    }
    normalized, errors = validate_ledger_entry(draft)
    if errors or not normalized:
        raise ValueError("; ".join(errors or ["invalid spend interval"]))
    path = _path_for(eid, base_dir)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    out = dict(normalized)
    out["path"] = str(path)
    return out


def record_jev_score(
    *,
    jev_score: float,
    run_id: str | None = None,
    cloud_agent_id: str | None = None,
    lifecycle_task_type: str = "",
    jev_suggested_tier: str | None = None,
    jev_model: str | None = None,
    jev_route_clarity: str | None = None,
    tier: str | None = None,
    model: str | None = None,
    route_clarity: str | None = None,
    hardware: str | None = None,
    effort: str | None = None,
    outcome_accepted: bool | None = None,
    related_issue: int | None = None,
    related_pr: int | None = None,
    session: str = "",
    metadata: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Append Jev shadow scores on a spend_interval row (#1356); does not affect routing."""
    if jev_score is None:
        raise ValueError("jev_score is required")
    if not (run_id or cloud_agent_id):
        raise ValueError("run_id or cloud_agent_id is required for Jev score attribution")
    meta = dict(metadata or {})
    meta.setdefault("jev_shadow_mode", True)
    return record_spend_interval(
        cloud_agent_id=cloud_agent_id,
        run_id=run_id,
        lifecycle_task_type=lifecycle_task_type,
        model=model,
        tier=tier,
        effort=effort,
        hardware=hardware,
        route_clarity=route_clarity,
        outcome_accepted=None,
        jev_score=jev_score,
        jev_suggested_tier=jev_suggested_tier,
        jev_model=jev_model,
        jev_route_clarity=jev_route_clarity,
        related_issue=related_issue,
        related_pr=related_pr,
        session=session,
        metadata=meta,
        base_dir=base_dir,
    )


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
        data = _read_ledger_file(path)
        if not data:
            return None
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
        data = _read_ledger_file(f)
        if not data:
            continue
        if ledger_record_type(data) != RECORD_TYPE_DECISION:
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


def list_spend_intervals(
    *,
    run_id: str | None = None,
    cloud_agent_id: str | None = None,
    lifecycle_task_type: str | None = None,
    outcome_accepted: bool | None = None,
    jev_scored: bool | None = None,
    limit: int = 200,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """List spend interval ledger rows newest-first (#1352)."""
    d = _ensure_dir(base_dir)
    rows: list[dict[str, Any]] = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = _read_ledger_file(f)
        if not data or ledger_record_type(data) != RECORD_TYPE_SPEND_INTERVAL:
            continue
        if run_id is not None and data.get("run_id") != run_id:
            continue
        if cloud_agent_id is not None and data.get("cloud_agent_id") != cloud_agent_id:
            continue
        if lifecycle_task_type and data.get("lifecycle_task_type") != lifecycle_task_type:
            continue
        if outcome_accepted is not None and data.get("outcome_accepted") is not outcome_accepted:
            continue
        if jev_scored is True and not spend_interval_has_jev_score(data):
            continue
        if jev_scored is False and spend_interval_has_jev_score(data):
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
