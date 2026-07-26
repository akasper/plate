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


# Heuristic handoff token costs by risk (#634/#644 parity with feature/bug loops).
_HANDOFF_ESTIMATE_BASE: dict[str, int] = {
    "low": 2000,
    "medium": 5000,
    "high": 12000,
    "critical": 20000,
}


def estimate_handoff_cost(
    *,
    to_agent: str = "",
    risk: str = "medium",
    budget_tokens: int | None = None,
) -> dict[str, Any]:
    """Advisory token estimate for a fleet handoff (#634/#644)."""
    if budget_tokens is not None:
        try:
            tokens = max(0, int(budget_tokens))
        except (TypeError, ValueError):
            tokens = _HANDOFF_ESTIMATE_BASE["medium"]
        return {
            "ok": True,
            "to_agent": to_agent,
            "risk": (risk or "medium").lower(),
            "estimated_tokens": tokens,
            "source": "explicit",
        }
    risk_n = (risk or "medium").lower()
    if risk_n not in _HANDOFF_ESTIMATE_BASE:
        risk_n = "medium"
    tokens = _HANDOFF_ESTIMATE_BASE[risk_n]
    role = get_fleet_role((to_agent or "").strip())
    if role and role.get("default_token_share"):
        # Scale medium baseline by role share relative to implementer 0.35
        try:
            share = float(role.get("default_token_share") or 0.15)
            tokens = max(500, int(_HANDOFF_ESTIMATE_BASE["medium"] * (share / 0.35)))
            if risk_n == "high":
                tokens = int(tokens * 1.5)
            elif risk_n == "critical":
                tokens = int(tokens * 2.0)
            elif risk_n == "low":
                tokens = max(500, int(tokens * 0.6))
        except (TypeError, ValueError):
            pass
    return {
        "ok": True,
        "to_agent": to_agent,
        "risk": risk_n,
        "estimated_tokens": int(tokens),
        "source": "heuristic",
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine enforce hard ceilings.",
            "create_handoff hydrates remaining via get_budget_snapshot when use_live_budget.",
        ],
    }


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
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
    open_checkpoint: bool = False,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Create an explicit agent→agent handoff packet.

    #634: when ``budget_remaining`` is omitted and ``use_live_budget`` is True (default),
    hydrate remaining tokens from durable budget snapshot. When ``budget_tokens`` is
    omitted, fill from ``estimate_handoff_cost``. Gate when est exceeds remaining.
    """
    fa = (from_agent or "orchestrator").strip()
    ta = (to_agent or "").strip()
    task_s = (task or "").strip()
    if not ta:
        return {"ok": False, "error": "to_agent required"}
    if not task_s:
        return {"ok": False, "error": "task required"}

    risk_n = (risk or "medium").lower()
    need_human = bool(requires_human) or risk_n in ("high", "critical")

    # Isolate budget + ledger under fleet base_dir when provided so tests /
    # alternate roots never charge or write repo-root .agentic/budget|ledger.
    budget_base: Path | None = None
    ledger_base: Path | None = None
    if base_dir is not None:
        root = Path(base_dir)
        budget_base = root / "budget"
        ledger_base = root / "ledger"

    cost_est = estimate_handoff_cost(
        to_agent=ta, risk=risk_n, budget_tokens=budget_tokens
    )
    effective_tokens = budget_tokens
    if effective_tokens is None:
        effective_tokens = int(cost_est.get("estimated_tokens") or 0)

    effective_remaining = budget_remaining
    budget_notes: list[str] = []
    surface_budget_pause = False
    surface_budget_pressure: str | None = None
    if effective_remaining is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(
                estimate_tokens=int(effective_tokens or 0),
                base_dir=budget_base,
            )
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective_remaining = int(rem)
                budget_notes.append(
                    f"budget hydrated: remaining_tokens={effective_remaining} "
                    f"pressure={snap.get('budget_pressure')}"
                )
            # #634/#869: honor durable next-cycle pause rails (same as loops/PM/engine)
            surface_budget_pressure = (
                str(snap.get("budget_pressure") or "").lower() or None
            )
            would_pause = bool(
                snap.get("would_pause_next_cycle")
                if snap.get("would_pause_next_cycle") is not None
                else snap.get("would_pause")
            )
            if (
                surface_budget_pressure in ("critical", "exhausted")
                or would_pause
                or (effective_remaining is not None and int(effective_remaining) <= 0)
            ):
                surface_budget_pause = True
                budget_notes.append(
                    snap.get("gate_reason")
                    or "blocked: durable budget would_pause / pressure gate"
                )
        except Exception as exc:
            budget_notes.append(f"budget hydrate skipped: {exc}")

    # #644/#634: hard budget gate before opening work
    if surface_budget_pause:
        rem_out = (
            int(effective_remaining) if effective_remaining is not None else 0
        )
        return {
            "ok": False,
            "error": (
                f"budget: durable rails pause handoff "
                f"(pressure={surface_budget_pressure} remaining={rem_out})"
            ),
            "blocked": True,
            "reason": "budget",
            "cost_estimate_tokens": int(effective_tokens) if effective_tokens is not None else None,
            "budget_remaining": rem_out,
            "budget_pressure": surface_budget_pressure,
            "would_pause_next_cycle": True,
            "cost_estimate": cost_est,
            "notes": budget_notes,
        }
    if (
        effective_remaining is not None
        and effective_tokens is not None
        and int(effective_tokens) > int(effective_remaining)
    ):
        return {
            "ok": False,
            "error": (
                f"budget_tokens {effective_tokens} exceeds remaining {effective_remaining}"
            ),
            "blocked": True,
            "reason": "budget",
            "cost_estimate_tokens": int(effective_tokens),
            "budget_remaining": int(effective_remaining),
            "cost_estimate": cost_est,
            "notes": budget_notes,
        }

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
        budget_tokens=int(effective_tokens) if effective_tokens is not None else None,
        risk=risk_n,
        related_issue=related_issue,
        related_pr=related_pr,
        parent_handoff_id=parent_handoff_id,
        requires_human=need_human,
        created_at=ts,
        updated_at=ts,
    )
    if role:
        packet.context.setdefault("to_role", role)
    if budget_notes:
        packet.context.setdefault("budget_notes", budget_notes)
    if effective_remaining is not None:
        packet.context.setdefault("budget_remaining_at_create", int(effective_remaining))

    # High-risk / human handoffs start blocked until accept or checkpoint approve
    if need_human and risk_n in ("high", "critical"):
        packet.status = "blocked"
        packet.context.setdefault(
            "block_reason", "requires_human_or_high_risk_until_accepted"
        )

    data = _load(base_dir)
    data["handoffs"].append(packet.to_dict())
    _save(data, base_dir)

    out: dict[str, Any] = {
        "ok": True,
        "handoff": packet.to_dict(),
        "marker": render_handoff_marker(packet),
        "cost_estimate_tokens": int(effective_tokens) if effective_tokens is not None else None,
        "budget_remaining": (
            int(effective_remaining) if effective_remaining is not None else None
        ),
        "cost_estimate": cost_est,
        "notes": list(budget_notes),
        "delegation_hint": (
            f"plate_delegate_to_agent / gh plate agents delegate {ta} "
            f"--task {json.dumps(task_s)[:80]}"
        ),
    }
    try:
        from .autonomy import apply_live_budget_charge

        apply_live_budget_charge(
            out,
            tokens=int(effective_tokens or 0),
            use_live_budget=use_live_budget,
            action_kind="fleet_handoff",
            reason=f"create_handoff:{packet.handoff_id}",
            base_dir=budget_base,
        )
    except Exception:
        pass

    if open_checkpoint or (need_human and risk_n in ("high", "critical")):
        try:
            from .checkpoint import create_checkpoint

            # Isolate checkpoints under fleet base_dir when provided so tests /
            # alternate roots never pollute repo-root .agentic/checkpoints
            # (which pause PM/AutonomyEngine via pause_autonomy).
            cp_base = None
            if base_dir is not None:
                cp_base = Path(base_dir) / "checkpoints"
            cp = create_checkpoint(
                title=f"Fleet handoff {fa} → {ta}",
                reason=task_s[:200],
                impact="high" if risk_n in ("high", "critical") else "medium",
                action_kind="fleet_handoff",
                related_issue=related_issue,
                related_pr=related_pr,
                scope={
                    "handoff_id": packet.handoff_id,
                    "to_agent": ta,
                    "budget_tokens": packet.budget_tokens,
                    "budget_remaining": effective_remaining,
                },
                created_by="fleet",
                pause_autonomy=True,
                base_dir=cp_base,
            )
            if isinstance(cp, dict) and cp.get("id"):
                out["checkpoint_id"] = cp["id"]
                # store on packet
                for h in data["handoffs"]:
                    if h.get("handoff_id") == packet.handoff_id:
                        h.setdefault("context", {})["checkpoint_id"] = cp["id"]
                        h["updated_at"] = _now()
                        out["handoff"] = h
                        break
                _save(data, base_dir)
        except Exception:
            pass

    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="fleet_handoff",
                decision="delegate" if packet.status == "open" else "pause",
                reason=f"handoff {fa} → {ta}: {task_s[:120]}",
                sources=["fleet", "#644", "#634"],
                risk_tolerance=packet.risk,
                impact=packet.risk,
                related_issue=related_issue,
                related_pr=related_pr,
                cost_estimate_tokens=packet.budget_tokens,
                checkpoint_id=out.get("checkpoint_id"),
                actor="fleet",
                metadata={
                    "handoff_id": packet.handoff_id,
                    "to_agent": ta,
                    "budget_remaining": effective_remaining,
                },
                base_dir=ledger_base,
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass

    return out


def dispatch_work_from_handoff(
    handoff: dict[str, Any],
    *,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
    artifact_base_dir: Path | None = None,
    budget_base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Open real work surfaces when a fleet handoff is accepted (#644 residual).

    - implementer (or implement/fix/build task) → feature or bug loop (#638/#639)
    - researcher / design personas → #632 design or research artifact proposal
    - reviewer → babysit hint only (no auto PR mutation)
    - deployer/planner/market → packet hint only (ceremony/human gates)

    Never merges or auto-approves; durable ids stored on handoff.context.
    """
    if not isinstance(handoff, dict):
        return {"ok": False, "error": "handoff required"}
    to_agent = str(handoff.get("to_agent") or "").lower().strip()
    task = str(handoff.get("task") or "")
    task_l = task.lower()
    related = handoff.get("related_issue")
    try:
        issue_n = int(related) if related is not None else None
    except (TypeError, ValueError):
        issue_n = None
    # Remaining pool for gates: prefer create-time remaining, never budget_tokens (allocation)
    ctx0 = dict(handoff.get("context") or {})
    rem_raw = ctx0.get("budget_remaining_at_create")
    try:
        remaining_i = int(rem_raw) if rem_raw is not None else None
    except (TypeError, ValueError):
        remaining_i = None
    use_live = remaining_i is None
    risk = str(handoff.get("risk") or "medium").lower()
    if risk not in ("low", "medium", "high"):
        risk = "medium"
    hid = handoff.get("handoff_id")
    ctx = dict(ctx0)

    # Researcher / design → pending artifact for human approval
    want_design = to_agent in ("designer", "design-minimal", "design-storyteller") or (
        "design" in task_l and to_agent in ("planner", "researcher", "market-monitor")
    )
    want_research = to_agent in ("researcher", "research-analyst", "market-monitor") or any(
        k in task_l for k in ("research", "survey", "competitor", "market signal")
    )
    if want_design or (want_research and not any(k in task_l for k in ("implement", "bug", "fix"))):
        kind = "design" if want_design else "research"
        try:
            from .design_research_approval import propose_artifact

            out = propose_artifact(
                kind,
                title=task[:120] or f"{kind} from fleet",
                summary=task[:2000] or f"Fleet handoff {hid} → {kind}",
                related_issue=issue_n,
                actor="fleet",
                base_dir=artifact_base_dir,
                budget_remaining=remaining_i,
                use_live_budget=use_live,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "dispatch_kind": "artifact"}
        if out.get("blocked") or out.get("reason") == "budget":
            return {
                "ok": False,
                "blocked": True,
                "dispatch_kind": "artifact",
                "error": out.get("error") or out.get("reason") or "budget",
                "result": out,
            }
        pid = out.get("id")
        ctx["dispatched"] = "artifact"
        ctx["artifact_proposal_id"] = pid
        ctx["artifact_kind"] = kind
        if record_ledger:
            try:
                from .ledger import record_decision

                record_decision(
                    action_kind="fleet_dispatch_artifact",
                    decision="proposed",
                    reason=f"handoff {hid} → {kind} artifact {pid}",
                    sources=["fleet", "#644", "#632"],
                    actor="fleet",
                    related_issue=issue_n,
                    cost_estimate_tokens=out.get("cost_estimate_tokens"),
                    metadata={"handoff_id": hid, "proposal_id": pid},
                )
            except Exception:
                pass
        return {
            "ok": bool(out.get("ok", True)),
            "dispatch_kind": "artifact",
            "run_id": pid,
            "stage": out.get("status") or "pending",
            "context_patch": ctx,
            "ask_user_question": out.get("ask_user_question"),
            "result": out,
        }

    # Implementer → feature or bug loop
    want_bug = to_agent in ("implementer",) and any(
        k in task_l for k in ("bug", "fix", "regression", "flake")
    )
    want_impl = to_agent in (
        "implementer",
        "dev-cautious",
        "dev-pragmatic",
        "dev-refactorer",
    ) or any(k in task_l for k in ("implement", "build", "code", "feature", "ship"))
    if want_bug:
        try:
            from .bug_loop import start_bug_loop

            out = start_bug_loop(
                bug_number=issue_n,
                bug_title=task[:200] or "Fleet bugfix",
                risk=risk,
                risk_tolerance=risk,
                budget_remaining=remaining_i,
                use_live_budget=use_live,
                budget_base_dir=budget_base_dir,
                base_dir=bug_loop_base_dir,
                record_ledger=record_ledger,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "dispatch_kind": "bug_loop"}
        run = out.get("run") or {}
        rid = run.get("id")
        ctx["dispatched"] = "bug_loop"
        ctx["loop_run_id"] = rid
        ctx["loop_kind"] = "bug"
        return {
            "ok": bool(out.get("ok", True)),
            "dispatch_kind": "bug_loop",
            "run_id": rid,
            "stage": run.get("stage"),
            "blocked": bool(out.get("blocked")),
            "error": out.get("error"),
            "context_patch": ctx,
            "result": out,
        }
    if want_impl:
        try:
            from .feature_loop import start_feature_loop

            out = start_feature_loop(
                feature_number=issue_n,
                feature_title=task[:200] or "Fleet implement",
                risk=risk,
                size="medium",
                risk_tolerance=risk,
                needs_media_approval=False,
                budget_remaining=remaining_i,
                use_live_budget=use_live,
                budget_base_dir=budget_base_dir,
                base_dir=feature_loop_base_dir,
                record_ledger=record_ledger,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "dispatch_kind": "feature_loop"}
        run = out.get("run") or {}
        rid = run.get("id")
        ctx["dispatched"] = "feature_loop"
        ctx["loop_run_id"] = rid
        ctx["loop_kind"] = "feature"
        return {
            "ok": bool(out.get("ok", True)),
            "dispatch_kind": "feature_loop",
            "run_id": rid,
            "stage": run.get("stage"),
            "blocked": bool(out.get("blocked")),
            "error": out.get("error"),
            "context_patch": ctx,
            "result": out,
        }

    if to_agent == "reviewer" or "babysit" in task_l or "review" in task_l:
        pr = handoff.get("related_pr")
        hint = (
            f"gh plate pr babysit {pr} --act"
            if pr
            else "gh plate pr babysit <N> --act / plate_pr_babysit"
        )
        ctx["dispatched"] = "babysit_hint"
        ctx["babysit_hint"] = hint
        return {
            "ok": True,
            "dispatch_kind": "babysit_hint",
            "hint": hint,
            "context_patch": ctx,
        }

    ctx["dispatched"] = "packet_only"
    return {
        "ok": True,
        "dispatch_kind": "packet_only",
        "reason": f"to_agent={to_agent} has no auto work surface; execute packet manually",
        "context_patch": ctx,
    }


def update_handoff(
    handoff_id: str,
    *,
    status: str | None = None,
    notes: str | None = None,
    artifacts: list[str] | None = None,
    context_patch: dict[str, Any] | None = None,
    base_dir: Path | None = None,
    record_ledger: bool = True,
    dispatch_work: bool = True,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
    artifact_base_dir: Path | None = None,
    budget_base_dir: Path | None = None,
) -> dict[str, Any]:
    """Accept/complete/block/cancel a handoff.

    When status becomes ``accepted`` and ``dispatch_work`` is True, open the matching
    work surface (feature/bug loop, artifact proposal, or babysit hint) (#644).
    """
    data = _load(base_dir)
    hid = (handoff_id or "").strip()
    found: dict[str, Any] | None = None
    for h in data["handoffs"]:
        if h.get("handoff_id") == hid:
            found = h
            break
    if not found:
        return {"ok": False, "error": f"handoff not found: {hid}"}

    became_accepted = False
    if status:
        st = status.lower().strip()
        if st not in ("open", "accepted", "done", "blocked", "cancelled"):
            return {"ok": False, "error": f"invalid status: {status}"}
        # Accepting a blocked human/high-risk handoff clears block
        if st == "accepted" and found.get("status") == "blocked":
            ctx = dict(found.get("context") or {})
            ctx.pop("block_reason", None)
            found["context"] = ctx
        if st == "accepted" and found.get("status") != "accepted":
            became_accepted = True
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

    # #644 residual: accept → open durable work surface once (idempotent via context.dispatched)
    if became_accepted and dispatch_work:
        existing_ctx = dict(found.get("context") or {})
        if existing_ctx.get("dispatched"):
            out["dispatch"] = {
                "ok": True,
                "skipped": True,
                "reason": "already_dispatched",
                "dispatch_kind": existing_ctx.get("dispatched"),
            }
        else:
            try:
                disp = dispatch_work_from_handoff(
                    found,
                    feature_loop_base_dir=feature_loop_base_dir,
                    bug_loop_base_dir=bug_loop_base_dir,
                    artifact_base_dir=artifact_base_dir,
                    budget_base_dir=budget_base_dir,
                    record_ledger=record_ledger,
                )
            except Exception as exc:
                disp = {"ok": False, "error": str(exc)}
            out["dispatch"] = disp
            patch = disp.get("context_patch") if isinstance(disp, dict) else None
            if isinstance(patch, dict) and patch:
                # reload + persist patch
                data2 = _load(base_dir)
                for h in data2["handoffs"]:
                    if h.get("handoff_id") == hid:
                        ctx2 = dict(h.get("context") or {})
                        ctx2.update(patch)
                        h["context"] = ctx2
                        h["updated_at"] = _now()
                        out["handoff"] = h
                        break
                _save(data2, base_dir)
            if isinstance(disp, dict) and disp.get("blocked"):
                # surface budget block without undoing accept
                out.setdefault("notes", [])
                if isinstance(out["notes"], list):
                    out["notes"].append(disp.get("error") or "dispatch blocked")
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
                # include blocked so feed/orchestrator can surface human gates (#644)
                if st not in ("open", "accepted", "blocked"):
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
    budget_tokens: int | None = None,
    risk_tolerance: str = "medium",
    related_issue: int | None = None,
    base_dir: Path | None = None,
    create: bool = False,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Map a high-level user intent to a multi-agent handoff plan (example flow #644).

    create=False → dry plan only; create=True → write open handoffs.

    #634: when ``budget_tokens`` is omitted and ``use_live_budget`` is True (default),
    hydrate total pool from durable remaining tokens so fleet plans honor AutonomyEngine rails.
    Explicit ``budget_tokens`` wins. Block create when remaining is 0.
    """
    text = (intent or "").lower()
    steps: list[dict[str, Any]] = []
    budget_notes: list[str] = []
    effective_budget = budget_tokens
    budget_base: Path | None = None
    surface_budget_pause = False
    surface_budget_pressure: str | None = None
    if base_dir is not None:
        budget_base = Path(base_dir) / "budget"
    if effective_budget is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(base_dir=budget_base)
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective_budget = int(rem)
                budget_notes.append(
                    f"budget hydrated: remaining_tokens={effective_budget} "
                    f"pressure={snap.get('budget_pressure')}"
                )
            # #634/#869: block fleet plan/create when next cycle cannot fund work
            # (independent of risk_tolerance; mirrors loops/PM/AutonomyEngine).
            surface_budget_pressure = (
                str(snap.get("budget_pressure") or "").lower() or None
            )
            would_pause = bool(
                snap.get("would_pause_next_cycle")
                if snap.get("would_pause_next_cycle") is not None
                else snap.get("would_pause")
            )
            if (
                surface_budget_pressure in ("critical", "exhausted")
                or would_pause
                or (effective_budget is not None and int(effective_budget) <= 0)
            ):
                surface_budget_pause = True
                budget_notes.append(
                    snap.get("gate_reason")
                    or "blocked: durable budget would_pause / pressure gate"
                )
        except Exception as exc:
            budget_notes.append(f"budget hydrate skipped: {exc}")
    if effective_budget is None:
        effective_budget = 20000
        budget_notes.append("budget defaulted to 20000 (no live remaining)")

    # Always start with planner unless pure ops
    want_research = any(k in text for k in ("market", "research", "discuss", "competitor"))
    want_design = any(k in text for k in ("design", "wireframe", "ux", "visual", "mock"))
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
    if want_design:
        steps.append(
            {
                "to_agent": "researcher",
                "task": f"Produce design artifact for approval: {intent[:200]}",
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

    # Zero remaining or durable pause rails: plan shape only, do not allocate or create
    if int(effective_budget) <= 0 or surface_budget_pause:
        plan = [
            {
                **s,
                "budget_tokens": 0,
                "from_agent": "orchestrator",
                "related_issue": related_issue,
            }
            for s in steps
        ]
        rem_out = int(effective_budget) if not surface_budget_pause else int(effective_budget)
        err = (
            f"budget: remaining {rem_out} tokens; cannot allocate fleet"
            if not surface_budget_pause
            else (
                f"budget: durable rails pause fleet "
                f"(pressure={surface_budget_pressure} remaining={rem_out})"
            )
        )
        return {
            "ok": False,
            "blocked": True,
            "reason": "budget",
            "error": err,
            "intent": intent,
            "plan": plan,
            "budget": None,
            "budget_remaining_tokens": rem_out,
            "budget_pressure": surface_budget_pressure,
            "would_pause_next_cycle": bool(surface_budget_pause),
            "created": [],
            "n_created": 0,
            "dry_run": not create,
            "notes": budget_notes,
        }

    alloc = allocate_fleet_budget(
        int(effective_budget),
        active_roles=[s["to_agent"] for s in steps],
        risk_tolerance=risk_tolerance,
    )
    by_id = {a["agent_id"]: a for a in alloc.get("allocations") or []}

    plan = []
    created = []
    skipped: list[dict[str, Any]] = []
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
                # Pool already live-hydrated; pass remaining so handoffs share the same gate
                budget_remaining=int(effective_budget),
                use_live_budget=False,
                context={"intent": intent, "plan_step": True},
                base_dir=base_dir,
            )
            if r.get("ok"):
                created.append(r.get("handoff"))
            else:
                skipped.append(
                    {
                        "to_agent": s["to_agent"],
                        "error": r.get("error"),
                        "reason": r.get("reason"),
                    }
                )

    return {
        "ok": True,
        "intent": intent,
        "plan": plan,
        "budget": alloc,
        "budget_remaining_tokens": int(effective_budget),
        "created": created,
        "n_created": len(created),
        "skipped": skipped,
        "dry_run": not create,
        "notes": budget_notes,
    }


def fleet_status(
    *,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
    risk_tolerance: str = "medium",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Aggregate fleet roles + active handoffs + budget allocation snapshot.

    #634: when budget_remaining omitted and use_live_budget, hydrate remaining
    from durable spend so status/allocation matches AutonomyEngine rails.
    """
    active = list_handoffs(status="active", limit=100, base_dir=base_dir)
    by_agent: dict[str, int] = {}
    human_needed = 0
    for h in active:
        ta = str(h.get("to_agent") or "?")
        by_agent[ta] = by_agent.get(ta, 0) + 1
        if h.get("requires_human") or h.get("status") == "blocked":
            human_needed += 1

    effective_remaining = budget_remaining
    budget_base: Path | None = None
    if base_dir is not None:
        budget_base = Path(base_dir) / "budget"
    if effective_remaining is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(base_dir=budget_base)
            rem = snap.get("remaining_tokens")
            if rem is not None:
                effective_remaining = int(rem)
        except Exception:
            pass

    budget = None
    if effective_remaining is not None:
        budget = allocate_fleet_budget(
            effective_remaining,
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
        "budget_remaining_tokens": effective_remaining,
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
        cp = (h.get("context") or {}).get("checkpoint_id")
        options = [
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
                "id": "block",
                "label": "Block",
                "description": f"plate_fleet_update {hid} --status blocked",
            },
            {
                "id": "cancel",
                "label": "Cancel",
                "description": f"plate_fleet_update {hid} --status cancelled",
            },
        ]
        if cp:
            options.insert(
                0,
                {
                    "id": "decide_checkpoint",
                    "label": "Decide checkpoint",
                    "description": f"plate_checkpoint_decide {cp} approve|reject",
                },
            )
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
                "rank": 10 if h.get("status") == "blocked" else 18,
                "badges": ["fleet", "handoff", str(h.get("status")), str(h.get("to_agent"))],
                "source": "fleet_handoffs",
                "impact": "high" if h.get("requires_human") or h.get("status") == "blocked" else "medium",
                "reason": h.get("task") or title,
                "checkpoint_id": cp,
                "ask_user_question": {
                    "question": f"{title}: {str(h.get('task') or '')[:120]}",
                    "options": options,
                },
                "marker": render_handoff_marker(h),
            }
        )
        if len(items) >= limit:
            break
    return items


def handoff_from_pm_assignment(
    assignment: dict[str, Any],
    *,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
    open_checkpoint: bool = False,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Bridge #660 PM assignment → #644 fleet handoff packet.

    Maps PM persona agent_id to fleet role when possible; otherwise uses agent_id
    as free-form to_agent. Does not complete the PM assignment.
    Live #634 budget hydrate when budget_remaining omitted (use_live_budget).
    """
    if not assignment:
        return {"ok": False, "error": "assignment required"}
    agent = str(assignment.get("agent_id") or assignment.get("to_agent") or "").strip()
    # Map PM personas → fleet roles
    persona_to_role = {
        "dev-cautious": "implementer",
        "dev-pragmatic": "implementer",
        "dev-refactorer": "implementer",
        # Design personas open #632 artifacts on accept (not planner stubs)
        "design-minimal": "researcher",
        "design-storyteller": "researcher",
        "research-analyst": "researcher",
        "release-engineer": "deployer",
        "pm-orchestrator": "planner",
    }
    to_agent = persona_to_role.get(agent, agent or "implementer")
    task = str(
        assignment.get("work_title")
        or assignment.get("task")
        or assignment.get("packet", {}).get("prompt_segment")
        or "PM assignment"
    )
    budget = assignment.get("estimated_tokens")
    risk = str(assignment.get("risk") or assignment.get("impact") or "medium")
    related = assignment.get("related_issue") or assignment.get("work_id")
    related_issue = None
    if related is not None:
        try:
            related_issue = int(str(related).lstrip("#"))
        except (TypeError, ValueError):
            related_issue = None
    out = create_handoff(
        from_agent="pm-orchestrator",
        to_agent=to_agent,
        task=task[:500],
        budget_tokens=int(budget) if budget is not None else None,
        risk=risk,
        related_issue=related_issue,
        requires_human=bool(assignment.get("requires_checkpoint")),
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget if budget_remaining is None else False,
        open_checkpoint=open_checkpoint or bool(assignment.get("requires_checkpoint")),
        context={
            "pm_assignment_id": assignment.get("assignment_id"),
            "work_type": assignment.get("work_type"),
            "pm_agent_id": agent,
        },
        base_dir=base_dir,
        record_ledger=record_ledger,
    )
    if out.get("ok"):
        out["pm_assignment_id"] = assignment.get("assignment_id")
    return out
