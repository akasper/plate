"""Multi-agent fleet orchestration + handoff contracts (#644).

Coordinates specialized agents under the PM/Autonomy umbrella:
- Explicit handoff packets (narrow context, no hidden state)
- Durable handoff ledger under .agentic/fleet/
- Concurrent budget/risk allocation across fleet members
- Fleet status for orchestrator + endless feed

Does not execute remote agents itself — builds contracts agents/hosts honor.
GitHub remains source of truth for issues/PRs; this is local coordination state.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FLEET_DIR = Path(".agentic/fleet")
HANDOFFS_FILE = "handoffs.json"
MARKER_BEGIN = "<!-- PLATE-FLEET-HANDOFF:BEGIN -->"
MARKER_END = "<!-- PLATE-FLEET-HANDOFF:END -->"

# Fleet roles beyond PM TEAM (planner, implementer, reviewer, researcher, deployer, market)
FLEET_ROLES: list[dict[str, Any]] = [
    {
        "id": "planner",
        "role": "planner",
        "name": "Planner",
        "skills": ["plan", "epic", "release", "qanda"],
        "risk_bias": "low",
        "default_token_share": 0.15,
    },
    {
        "id": "implementer",
        "role": "implementer",
        "name": "Implementer",
        "skills": ["implement", "test", "bugfix"],
        "risk_bias": "medium",
        "default_token_share": 0.35,
    },
    {
        "id": "reviewer",
        "role": "reviewer",
        "name": "Reviewer",
        "skills": ["review", "babysit", "feedback"],
        "risk_bias": "low",
        "default_token_share": 0.15,
    },
    {
        "id": "researcher",
        "role": "researcher",
        "name": "Researcher",
        "skills": ["research", "market", "docs"],
        "risk_bias": "low",
        "default_token_share": 0.15,
    },
    {
        "id": "deployer",
        "role": "deployer",
        "name": "Deployer",
        "skills": ["deploy", "release", "packaging"],
        "risk_bias": "low",
        "default_token_share": 0.10,
    },
    {
        "id": "market-monitor",
        "role": "market",
        "name": "Market Monitor",
        "skills": ["market", "discussions", "signals"],
        "risk_bias": "low",
        "default_token_share": 0.10,
    },
]


@dataclass
class HandoffPacket:
    """Narrow context contract passed between agents."""

    handoff_id: str
    from_agent: str
    to_agent: str
    task: str
    status: str = "open"  # open | accepted | done | blocked | cancelled
    context: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    budget_tokens: int | None = None
    risk: str = "medium"
    related_issue: int | None = None
    related_pr: int | None = None
    parent_handoff_id: str | None = None
    requires_human: bool = False
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffPacket":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(base: Path | None = None) -> Path:
    d = base or FLEET_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store_path(base: Path | None = None) -> Path:
    d = base or FLEET_DIR
    if d.name == HANDOFFS_FILE:
        return d
    return d / HANDOFFS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "handoffs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "handoffs": []}
        data.setdefault("version", 1)
        data.setdefault("handoffs", [])
        if not isinstance(data["handoffs"], list):
            data["handoffs"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "handoffs": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def list_fleet_roles() -> list[dict[str, Any]]:
    return [dict(r) for r in FLEET_ROLES]


def get_fleet_role(agent_id: str) -> dict[str, Any] | None:
    for r in FLEET_ROLES:
        if r["id"] == agent_id or r["role"] == agent_id:
            return dict(r)
    return None


def render_handoff_marker(packet: dict[str, Any] | HandoffPacket) -> str:
    data = packet.to_dict() if isinstance(packet, HandoffPacket) else dict(packet)
    return f"{MARKER_BEGIN}\n{json.dumps(data, indent=2)}\n{MARKER_END}\n"


def create_handoff(
    *,
    from_agent: str,
    to_agent: str,
    task: str,
    context: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
    constraints: list[str] | None = None,
    budget_tokens: int | None = None,
    risk: str = "medium",
    related_issue: int | None = None,
    related_pr: int | None = None,
    parent_handoff_id: str | None = None,
    requires_human: bool = False,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Create an explicit agent→agent handoff packet."""
    fa = (from_agent or "orchestrator").strip()
    ta = (to_agent or "").strip()
    task_s = (task or "").strip()
    if not ta:
        return {"ok": False, "error": "to_agent required"}
    if not task_s:
        return {"ok": False, "error": "task required"}

    # Soft validate role ids (allow free-form for host agents)
    role = get_fleet_role(ta)
    ts = _now()
    packet = HandoffPacket(
        handoff_id=f"ho-{uuid.uuid4().hex[:10]}",
        from_agent=fa,
        to_agent=ta,
        task=task_s,
        status="open",
        context=dict(context or {}),
        artifacts=list(artifacts or []),
        constraints=list(constraints or [])
        + (["quiet_ops", "github_as_truth"] if not constraints else []),
        budget_tokens=budget_tokens,
        risk=(risk or "medium").lower(),
        related_issue=related_issue,
        related_pr=related_pr,
        parent_handoff_id=parent_handoff_id,
        requires_human=bool(requires_human),
        created_at=ts,
        updated_at=ts,
    )
    if role:
        packet.context.setdefault("to_role", role)

    data = _load(base_dir)
    data["handoffs"].append(packet.to_dict())
    _save(data, base_dir)

    out: dict[str, Any] = {
        "ok": True,
        "handoff": packet.to_dict(),
        "marker": render_handoff_marker(packet),
        "delegation_hint": (
            f"plate_delegate_to_agent / gh plate agents delegate {ta} "
            f"--task {json.dumps(task_s)[:80]}"
        ),
    }

    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="fleet_handoff",
                decision="delegate",
                reason=f"handoff {fa} → {ta}: {task_s[:120]}",
                sources=["fleet", "#644"],
                risk_tolerance=packet.risk,
                impact=packet.risk,
                related_issue=related_issue,
                related_pr=related_pr,
                cost_estimate_tokens=budget_tokens,
                actor="fleet",
                metadata={"handoff_id": packet.handoff_id, "to_agent": ta},
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass

    return out


def update_handoff(
    handoff_id: str,
    *,
    status: str | None = None,
    notes: str | None = None,
    artifacts: list[str] | None = None,
    context_patch: dict[str, Any] | None = None,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Accept/complete/block/cancel a handoff."""
    data = _load(base_dir)
    hid = (handoff_id or "").strip()
    found: dict[str, Any] | None = None
    for h in data["handoffs"]:
        if h.get("handoff_id") == hid:
            found = h
            break
    if not found:
        return {"ok": False, "error": f"handoff not found: {hid}"}

    if status:
        st = status.lower().strip()
        if st not in ("open", "accepted", "done", "blocked", "cancelled"):
            return {"ok": False, "error": f"invalid status: {status}"}
        found["status"] = st
        if st in ("done", "cancelled"):
            found["completed_at"] = _now()
    if notes is not None:
        found["notes"] = notes
    if artifacts:
        existing = list(found.get("artifacts") or [])
        for a in artifacts:
            if a not in existing:
                existing.append(a)
        found["artifacts"] = existing
    if context_patch:
        ctx = dict(found.get("context") or {})
        ctx.update(context_patch)
        found["context"] = ctx
    found["updated_at"] = _now()
    _save(data, base_dir)

    out: dict[str, Any] = {"ok": True, "handoff": found, "marker": render_handoff_marker(found)}
    if record_ledger and status:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="fleet_handoff_update",
                decision=status.lower(),
                reason=f"handoff {hid} → {status}",
                sources=["fleet", "#644"],
                actor="fleet",
                metadata={"handoff_id": hid},
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass
    return out


def complete_handoff(
    handoff_id: str,
    *,
    notes: str = "",
    artifacts: list[str] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    return update_handoff(
        handoff_id,
        status="done",
        notes=notes,
        artifacts=artifacts,
        base_dir=base_dir,
    )


def list_handoffs(
    *,
    status: str = "open",
    to_agent: str | None = None,
    from_agent: str | None = None,
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    data = _load(base_dir)
    return _filter_handoffs(
        data.get("handoffs") or [],
        status=status,
        to_agent=to_agent,
        from_agent=from_agent,
        limit=limit,
    )


def _filter_handoffs(
    rows: list[dict[str, Any]],
    *,
    status: str,
    to_agent: str | None,
    from_agent: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for h in rows:
        st = h.get("status")
        if status and status != "all":
            if status == "active":
                if st not in ("open", "accepted"):
                    continue
            elif st != status:
                continue
        if to_agent and h.get("to_agent") != to_agent:
            continue
        if from_agent and h.get("from_agent") != from_agent:
            continue
        out.append(h)
    return out[: max(1, int(limit or 50))]


def allocate_fleet_budget(
    total_tokens: int,
    *,
    active_roles: list[str] | None = None,
    risk_tolerance: str = "medium",
) -> dict[str, Any]:
    """Split a token budget across fleet roles for concurrent work."""
    total = max(0, int(total_tokens or 0))
    roles = list_fleet_roles()
    if active_roles:
        want = {str(x).lower() for x in active_roles}
        roles = [r for r in roles if r["id"] in want or r["role"] in want]
    if not roles:
        return {"ok": False, "error": "no roles", "allocations": []}

    # Risk off: only researcher + planner
    if (risk_tolerance or "").lower() == "off":
        roles = [r for r in roles if r["id"] in ("planner", "researcher")]
        if not roles:
            roles = [list_fleet_roles()[0]]

    shares = [float(r.get("default_token_share") or 0.1) for r in roles]
    ssum = sum(shares) or 1.0
    allocations = []
    remaining = total
    for i, r in enumerate(roles):
        if i == len(roles) - 1:
            tokens = remaining
        else:
            tokens = int(total * (shares[i] / ssum))
            remaining -= tokens
        allocations.append(
            {
                "agent_id": r["id"],
                "role": r["role"],
                "name": r["name"],
                "tokens": tokens,
                "share": round(shares[i] / ssum, 4),
                "risk_bias": r.get("risk_bias"),
            }
        )
    return {
        "ok": True,
        "total_tokens": total,
        "risk_tolerance": risk_tolerance,
        "allocations": allocations,
        "n_agents": len(allocations),
    }


def plan_fleet_from_intent(
    intent: str,
    *,
    budget_tokens: int = 20000,
    risk_tolerance: str = "medium",
    related_issue: int | None = None,
    base_dir: Path | None = None,
    create: bool = False,
) -> dict[str, Any]:
    """Map a high-level user intent to a multi-agent handoff plan (example flow #644).

    create=False → dry plan only; create=True → write open handoffs.
    """
    text = (intent or "").lower()
    steps: list[dict[str, Any]] = []

    # Always start with planner unless pure ops
    want_research = any(k in text for k in ("market", "research", "discuss", "competitor"))
    want_plan = any(k in text for k in ("plan", "release", "epic", "feature", "roadmap")) or True
    want_impl = any(k in text for k in ("implement", "build", "code", "fix", "ship", "start"))
    want_review = any(k in text for k in ("review", "babysit", "pr", "feedback")) or want_impl
    want_deploy = any(k in text for k in ("deploy", "release", "cut", "publish"))

    if want_research:
        steps.append(
            {
                "to_agent": "researcher",
                "task": f"Research signals related to: {intent[:200]}",
                "risk": "low",
            }
        )
    if want_plan:
        steps.append(
            {
                "to_agent": "planner",
                "task": f"Plan work / stub issues from intent: {intent[:200]}",
                "risk": "low",
            }
        )
    if want_impl and (risk_tolerance or "").lower() != "off":
        steps.append(
            {
                "to_agent": "implementer",
                "task": f"Implement top ready Features for: {intent[:200]}",
                "risk": risk_tolerance or "medium",
            }
        )
    if want_review:
        steps.append(
            {
                "to_agent": "reviewer",
                "task": f"Babysit open PRs and summarize feedback for: {intent[:200]}",
                "risk": "low",
            }
        )
    if want_deploy and (risk_tolerance or "").lower() not in ("off", "low"):
        steps.append(
            {
                "to_agent": "deployer",
                "task": f"Prepare release/deploy steps for: {intent[:200]}",
                "risk": "medium",
                "requires_human": True,
            }
        )

    if not steps:
        steps.append(
            {
                "to_agent": "planner",
                "task": f"Clarify and plan: {intent[:200]}",
                "risk": "low",
            }
        )

    alloc = allocate_fleet_budget(
        budget_tokens,
        active_roles=[s["to_agent"] for s in steps],
        risk_tolerance=risk_tolerance,
    )
    by_id = {a["agent_id"]: a for a in alloc.get("allocations") or []}

    plan = []
    created = []
    for s in steps:
        tokens = (by_id.get(s["to_agent"]) or {}).get("tokens")
        entry = {
            **s,
            "budget_tokens": tokens,
            "from_agent": "orchestrator",
            "related_issue": related_issue,
        }
        plan.append(entry)
        if create:
            r = create_handoff(
                from_agent="orchestrator",
                to_agent=s["to_agent"],
                task=s["task"],
                budget_tokens=tokens,
                risk=s.get("risk") or "medium",
                related_issue=related_issue,
                requires_human=bool(s.get("requires_human")),
                context={"intent": intent, "plan_step": True},
                base_dir=base_dir,
            )
            if r.get("ok"):
                created.append(r.get("handoff"))

    return {
        "ok": True,
        "intent": intent,
        "plan": plan,
        "budget": alloc,
        "created": created,
        "n_created": len(created),
        "dry_run": not create,
    }


def fleet_status(
    *,
    budget_remaining: int | None = None,
    risk_tolerance: str = "medium",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Aggregate fleet roles + active handoffs + budget allocation snapshot."""
    active = list_handoffs(status="active", limit=100, base_dir=base_dir)
    by_agent: dict[str, int] = {}
    human_needed = 0
    for h in active:
        ta = str(h.get("to_agent") or "?")
        by_agent[ta] = by_agent.get(ta, 0) + 1
        if h.get("requires_human") or h.get("status") == "blocked":
            human_needed += 1

    budget = None
    if budget_remaining is not None:
        budget = allocate_fleet_budget(
            budget_remaining,
            active_roles=list(by_agent.keys()) or None,
            risk_tolerance=risk_tolerance,
        )

    return {
        "roles": list_fleet_roles(),
        "active_handoffs": active,
        "n_active": len(active),
        "by_agent": by_agent,
        "human_needed": human_needed,
        "budget": budget,
        "risk_tolerance": risk_tolerance,
    }


def handoff_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Present open/blocked handoffs needing human or orchestration attention."""
    items: list[dict[str, Any]] = []
    rows = list_handoffs(status="active", limit=limit * 2, base_dir=base_dir)
    # Prefer blocked / requires_human first
    rows = sorted(
        rows,
        key=lambda h: (
            0 if h.get("status") == "blocked" else 1,
            0 if h.get("requires_human") else 1,
            h.get("created_at") or "",
        ),
    )
    for h in rows:
        if not (h.get("requires_human") or h.get("status") in ("open", "blocked", "accepted")):
            continue
        hid = h.get("handoff_id")
        title = f"Fleet handoff: {h.get('from_agent')} → {h.get('to_agent')}"
        items.append(
            {
                "id": hid,
                "item_type": "fleet_handoff",
                "title": title,
                "task": h.get("task"),
                "status": h.get("status"),
                "to_agent": h.get("to_agent"),
                "from_agent": h.get("from_agent"),
                "requires_human": h.get("requires_human"),
                "badges": ["fleet", "handoff", str(h.get("status")), str(h.get("to_agent"))],
                "source": "fleet_handoffs",
                "impact": "high" if h.get("requires_human") or h.get("status") == "blocked" else "medium",
                "reason": h.get("task") or title,
                "ask_user_question": {
                    "question": f"{title}: {str(h.get('task') or '')[:120]}",
                    "options": [
                        {
                            "id": "accept",
                            "label": "Accept / run",
                            "description": f"plate_fleet_update {hid} --status accepted then execute",
                        },
                        {
                            "id": "done",
                            "label": "Mark done",
                            "description": f"plate_fleet_complete {hid}",
                        },
                        {
                            "id": "cancel",
                            "label": "Cancel",
                            "description": f"plate_fleet_update {hid} --status cancelled",
                        },
                    ],
                },
                "marker": render_handoff_marker(h),
            }
        )
        if len(items) >= limit:
            break
    return items
