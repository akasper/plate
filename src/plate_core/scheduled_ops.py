"""Scheduled autonomous operations catalog + run packets (#641).

Ops (via .agentic/procedures/ + AutonomyEngine):
- scheduled-refactor
- release-cut-prep
- release-finalize-prep
- deploy-production (always high/critical — checkpoint)
- marketing-site-deploy
- marketplace-package (human Tasks for real publish)
- implement-epic-slice

First slice: durable catalog, last-run ledger, dry-run agent packets with
risk/checkpoint gates. Does not auto-tag or force-deploy.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPS_DIR = Path(".agentic/scheduled_ops")
RUNS_FILE = "runs.json"
MARKER_BEGIN = "<!-- PLATE-SCHEDULED-OP:BEGIN -->"
MARKER_END = "<!-- PLATE-SCHEDULED-OP:END -->"

# Canonical op catalog (also mirrored as procedure JSON files)
OPS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "scheduled-refactor",
        "cadence": "weekly",
        "risk_level": "medium",
        "description": "Identify rearch/debt from health/drift; open TDD refactor PR; babysit low-risk merges",
        "requires_human": False,
        "impact": "medium",
        "steps": [
            "gh plate health + plate_perform_information_audit dry_run",
            "Pick one safe refactor; branch bug/ or feature/ from origin/release",
            "Add failing tests; implement; PR + babysit",
            "Checkpoint if touches AGENTS.md/workflows/SPEC",
        ],
        "tools": ["plate_health", "plate_pr_babysit", "plate_bug_loop_start"],
    },
    {
        "id": "release-cut-prep",
        "cadence": "manual",
        "risk_level": "high",
        "description": "Prepare release cut: fragments, notes+media (#635), version inference, draft Release PR checklist",
        "requires_human": True,
        "impact": "high",
        "steps": [
            "gh plate release status",
            "plate_release_media_manifest; approve pending media",
            "scripts/cut_release.py or gh plate release cut (dry-run first)",
            "Open Release PR draft to main with Release+Documentation labels when packaging",
            "Surface checkpoint: approve cut scope + notes",
        ],
        "tools": ["plate_release_status", "plate_release_media_manifest", "plate_checkpoint_create"],
    },
    {
        "id": "release-finalize-prep",
        "cadence": "manual",
        "risk_level": "high",
        "description": "Post-merge finalize checklist: tag, GitHub Release, branch reset, Next Release issue",
        "requires_human": True,
        "impact": "high",
        "steps": [
            "Confirm Release PR merged to main",
            "gh plate release finalize (or workflow tag path)",
            "Verify GitHub Release + media body",
            "Hard-reset release track as policy allows",
            "Ensure Next Release issue exists",
        ],
        "tools": ["plate_release_status", "plate_checkpoint_create"],
    },
    {
        "id": "deploy-production",
        "cadence": "manual",
        "risk_level": "critical",
        "description": "Production deploy (always shadow + checkpoint + human approve)",
        "requires_human": True,
        "impact": "critical",
        "steps": [
            "plate_autonomy_simulate deploy",
            "Open #648 checkpoint with shadow report",
            "Human approve; never auto-deploy at risk-off/low",
            "Run deploy skill / CI deploy only after approve",
        ],
        "tools": ["plate_autonomy_simulate", "plate_checkpoint_create"],
    },
    {
        "id": "marketing-site-deploy",
        "cadence": "manual",
        "risk_level": "high",
        "description": "Deploy marketing/docs site with release highlights + approved GIFs",
        "requires_human": True,
        "impact": "high",
        "steps": [
            "Collect approved release media markdown",
            "Update marketing claims only if reviewed (extension release_checks)",
            "Checkpoint before live publish",
            "Deploy via project deploy skill",
        ],
        "tools": ["plate_release_media_render", "plate_checkpoint_create"],
    },
    {
        "id": "marketplace-package",
        "cadence": "manual",
        "risk_level": "critical",
        "description": "Package for marketplace with media + adoption proof (#652); real publish is human Task (#380/#381/#626)",
        "requires_human": True,
        "impact": "critical",
        "steps": [
            "plate_packaging_build: narratives + approved media + onboarding proof + planning links",
            "plate_packaging_render for review markdown",
            "Surface on feed: plate_packaging_feed (PM approve_for_publish)",
            "Detect human blockers: plate_task_detect marketplace/PyPI",
            "Do NOT publish secrets; open Task issues for human publish",
            "Document package paths for human owner under .agentic/packaging/",
        ],
        "tools": [
            "plate_packaging_build",
            "plate_packaging_render",
            "plate_packaging_feed",
            "plate_packaging_decide",
            "plate_task_detect",
            "plate_task_create",
        ],
    },
    {
        "id": "implement-epic-slice",
        "cadence": "manual",
        "risk_level": "medium",
        "description": "Pick ready Feature under an Epic; run feature_loop until merge-eligible",
        "requires_human": False,
        "impact": "medium",
        "steps": [
            "plate_what_next / plate_pm_run_cycle dry_run",
            "plate_feature_loop_start for top ready Feature",
            "Execute stage packets (TDD, fragment, media, babysit)",
            "Stop at human_checkpoint when required",
        ],
        "tools": ["plate_feature_loop_start", "plate_pm_run_cycle", "plate_what_next"],
    },
]


@dataclass
class ScheduledOpRun:
    id: str
    op_id: str
    status: str = "planned"  # planned | running | done | blocked | cancelled
    dry_run: bool = True
    requires_human: bool = False
    checkpoint_id: str | None = None
    packet: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or OPS_DIR
    if d.name == RUNS_FILE:
        return d
    return d / RUNS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "runs": [], "last_run_by_op": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "runs": [], "last_run_by_op": {}}
        data.setdefault("version", 1)
        data.setdefault("runs", [])
        data.setdefault("last_run_by_op", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "runs": [], "last_run_by_op": {}}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_op_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def list_ops() -> list[dict[str, Any]]:
    return [dict(o) for o in OPS_CATALOG]


def get_op(op_id: str) -> dict[str, Any] | None:
    for o in OPS_CATALOG:
        if o["id"] == op_id:
            return dict(o)
    return None


def build_op_packet(op: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    oid = op["id"]
    return {
        "op_id": oid,
        "description": op.get("description"),
        "cadence": op.get("cadence"),
        "risk_level": op.get("risk_level"),
        "requires_human": op.get("requires_human"),
        "dry_run": dry_run,
        "steps": list(op.get("steps") or []),
        "tools": list(op.get("tools") or []),
        "ask_user_question": {
            "question": f"Run scheduled op '{oid}' ({op.get('risk_level')} risk)?",
            "options": [
                {
                    "id": "run",
                    "label": "Run packet (agent executes steps)",
                    "description": f"plate_scheduled_op_run {oid} dry_run={str(dry_run).lower()}",
                },
                {
                    "id": "checkpoint",
                    "label": "Open human checkpoint first",
                    "description": "plate_checkpoint_create for this op",
                },
                {
                    "id": "skip",
                    "label": "Skip this cycle",
                    "description": "Leave last_run untouched",
                },
            ],
        },
        "marker": render_op_marker(
            {"op_id": oid, "risk": op.get("risk_level"), "dry_run": dry_run}
        ),
    }


def plan_op(op_id: str, *, dry_run: bool = True) -> dict[str, Any]:
    op = get_op(op_id)
    if not op:
        return {"ok": False, "error": f"unknown op: {op_id}"}
    est = estimate_op_cost(op_id, dry_run=dry_run)
    return {
        "ok": True,
        "op": op,
        "packet": build_op_packet(op, dry_run=dry_run),
        "cost_estimate": est,
    }


# Heuristic token costs by risk (#634 / #641 parity with feature/bug loops).
_OP_ESTIMATE_BASE: dict[str, int] = {
    "low": 3000,
    "medium": 8000,
    "high": 15000,
    "critical": 25000,
}


def estimate_op_cost(
    op_id: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Upfront cost estimate for a scheduled op (#634/#641).

    Advisory tokens for budget gates; AutonomyEngine ceilings still apply on autonomy loops.
    dry_run packets are cheaper (planning-only) than apply runs.
    """
    op = get_op(op_id)
    if not op:
        return {
            "ok": False,
            "op_id": op_id,
            "estimated_tokens": 0,
            "error": f"unknown op: {op_id}",
        }
    risk = str(op.get("risk_level") or "medium").lower()
    if risk not in _OP_ESTIMATE_BASE:
        risk = "medium"
    base = _OP_ESTIMATE_BASE[risk]
    # dry_run: packet + shadow only; apply: full agent steps
    tokens = max(500, base // 4) if dry_run else base
    if bool(op.get("requires_human")) and not dry_run:
        tokens += 2000  # checkpoint / human coordination overhead
    return {
        "ok": True,
        "op_id": op_id,
        "risk_level": risk,
        "dry_run": dry_run,
        "estimated_tokens": int(tokens),
        "breakdown": {
            "base": base,
            "dry_run_discount": base - tokens if dry_run else 0,
            "human_overhead": 2000 if (bool(op.get("requires_human")) and not dry_run) else 0,
        },
        "notes": [
            "Estimate is advisory; durable spend.json + AutonomyEngine still enforce hard ceilings.",
            "Gate scheduled runs with budget_remaining / live hydrate (use_live_budget).",
        ],
    }


def run_scheduled_op(
    op_id: str,
    *,
    dry_run: bool = True,
    risk_tolerance: str = "medium",
    approved: bool = False,
    checkpoint_id: str | None = None,
    note: str = "",
    base_dir: Path | None = None,
    record_ledger: bool = True,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any]:
    """Start/record a scheduled op run. dry_run default — no side effects beyond local ledger.

    #634: when ``budget_remaining`` is omitted and ``use_live_budget`` is True (default),
    hydrate remaining tokens from durable budget snapshot and block if est exceeds remaining.
    Explicit ``budget_remaining`` wins; ``use_live_budget=False`` skips live hydrate.
    """
    op = get_op(op_id)
    if not op:
        return {"ok": False, "error": f"unknown op: {op_id}"}

    risk = str(op.get("risk_level") or "medium")
    needs_human = bool(op.get("requires_human")) or risk in ("high", "critical")
    rank = {"off": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    tol = rank.get((risk_tolerance or "medium").lower(), 0)
    op_rank = rank.get(risk.lower(), 2)

    cost_est = estimate_op_cost(op_id, dry_run=dry_run)
    est_tokens = int(cost_est.get("estimated_tokens") or 0)
    effective_budget = budget_remaining
    budget_notes: list[str] = []
    if effective_budget is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            budget_snap = get_budget_snapshot(estimate_tokens=est_tokens)
            rem = budget_snap.get("remaining_tokens")
            if rem is not None:
                effective_budget = int(rem)
                budget_notes.append(
                    f"budget hydrated: remaining_tokens={effective_budget} "
                    f"pressure={budget_snap.get('budget_pressure')}"
                )
            if budget_snap.get("would_pause_next_cycle") and effective_budget is not None:
                # Mirror dashboard pressure: treat would_pause as zero room for new spend
                if int(effective_budget) < est_tokens:
                    budget_notes.append("budget snapshot would_pause_next_cycle")
        except Exception as exc:
            budget_notes.append(f"budget hydrate skipped: {exc}")

    blocked = False
    reasons: list[str] = []
    if op_rank > tol and not approved:
        blocked = True
        reasons.append(f"op risk {risk} exceeds risk_tolerance {risk_tolerance}")
    if needs_human and not approved and not checkpoint_id:
        blocked = True
        reasons.append("requires human approval or checkpoint_id")
    if risk == "critical" and not approved:
        blocked = True
        reasons.append("critical op always needs explicit approved=true")
    if effective_budget is not None and est_tokens > int(effective_budget):
        blocked = True
        reasons.append(
            f"budget: est {est_tokens} tokens exceeds remaining {effective_budget}"
        )

    packet = build_op_packet(op, dry_run=dry_run)
    # #645: always attach a shadow/simulate preview for medium+ scheduled ops
    shadow_report: dict[str, Any] | None = None
    shadow_id: str | None = None
    if risk in ("medium", "high", "critical") or needs_human:
        try:
            from .autonomy import AutonomyEngine

            eng = AutonomyEngine(repo=None)
            eng.risk_tolerance = risk_tolerance
            eng.enabled = (risk_tolerance or "off").lower() not in ("off", "")
            eng.autonomy_config = {
                "enabled": eng.enabled,
                "risk_tolerance": risk_tolerance,
            }
            # Map op id to action_kind when catalog uses hyphens
            action_kind = str(op.get("action_kind") or op_id).replace("-", "_")
            shadow = eng.simulate_action(
                action_kind,
                scope={
                    "scheduled_op": op_id,
                    "risk_level": risk,
                    "procedure_risk": risk,
                    "skip_git_preview": False,
                },
            )
            shadow_report = shadow.to_dict()
            shadow_id = shadow.shadow_id
            packet = dict(packet)
            packet["shadow_id"] = shadow_id
            packet["shadow_report"] = {
                "shadow_id": shadow_id,
                "impact": shadow_report.get("impact"),
                "requires_approval": shadow_report.get("requires_approval"),
                "estimated_tokens": shadow_report.get("estimated_tokens"),
                "predicted_diff": shadow_report.get("predicted_diff"),
                "worktree_plan": shadow_report.get("worktree_plan"),
                "gate_preview": shadow_report.get("gate_preview"),
            }
        except Exception as exc:
            reasons.append(f"shadow preview unavailable: {exc}")

    ts = _now()
    merged_notes = list(budget_notes) + list(reasons) + ([note] if note else [])
    run = ScheduledOpRun(
        id=f"sop-{uuid.uuid4().hex[:10]}",
        op_id=op_id,
        status="blocked" if blocked else ("done" if dry_run else "running"),
        dry_run=dry_run,
        requires_human=needs_human,
        checkpoint_id=checkpoint_id,
        packet=packet,
        notes=merged_notes,
        created_at=ts,
        updated_at=ts,
        completed_at=ts if (dry_run and not blocked) else None,
        metadata={
            "risk_tolerance": risk_tolerance,
            "approved": approved,
            "shadow_id": shadow_id,
            "cost_estimate_tokens": est_tokens,
            "budget_remaining": effective_budget,
            "budget_source": (
                "explicit"
                if budget_remaining is not None
                else ("live" if use_live_budget else "none")
            ),
        },
    )
    if dry_run and not blocked:
        run.notes.append("dry_run complete: packet emitted; no remote side effects")
        if shadow_id:
            run.notes.append(f"shadow preview {shadow_id} attached")
        run.status = "done"

    data = _load(base_dir)
    data["runs"].append(run.to_dict())
    if not blocked:
        data["last_run_by_op"][op_id] = {
            "run_id": run.id,
            "at": ts,
            "dry_run": dry_run,
            "status": run.status,
        }
    _save(data, base_dir)

    out: dict[str, Any] = {
        "ok": not blocked,
        "blocked": blocked,
        "run": run.to_dict(),
        "packet": packet,
        "proc_id": op_id,
        "status": "blocked" if blocked else ("dry-run" if dry_run else "executed"),
        "cost_estimate_tokens": est_tokens,
        "cost_estimate": cost_est,
        "budget_remaining": effective_budget,
        "notes": list(merged_notes),
        "log_marker": (
            f"<!-- PLATE-PROCEDURE-RUN:{op_id} cadence={op.get('cadence')} "
            f"risk={risk} dry_run={dry_run} -->"
        ),
    }
    if shadow_report is not None:
        out["shadow_report"] = shadow_report
        out["shadow_id"] = shadow_id
    if blocked:
        out["error"] = "; ".join(reasons)
        out["reason"] = out["error"]
    elif use_live_budget and est_tokens > 0:
        try:
            from .autonomy import apply_live_budget_charge

            apply_live_budget_charge(
                out,
                tokens=est_tokens,
                use_live_budget=True,
                action_kind="scheduled_op",
                reason=f"run_scheduled_op:{op_id}:{run.id}",
            )
        except Exception:
            pass

    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="scheduled_op",
                decision="pause" if blocked else ("proceed" if not dry_run else "shadow"),
                reason=f"scheduled op {op_id}: {out.get('status')}",
                sources=["scheduled_ops", "#641", "#645", "#634"],
                risk_tolerance=risk_tolerance,
                impact=risk,
                checkpoint_id=checkpoint_id,
                shadow_id=shadow_id,
                actor="scheduled_ops",
                metadata={
                    "run_id": run.id,
                    "op_id": op_id,
                    "dry_run": dry_run,
                    "cost_estimate_tokens": est_tokens,
                    "budget_remaining": effective_budget,
                },
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass
    return out


def complete_op_run(
    run_id: str,
    *,
    status: str = "done",
    note: str = "",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    data = _load(base_dir)
    found = None
    for r in data["runs"]:
        if r.get("id") == run_id:
            found = r
            break
    if not found:
        return {"ok": False, "error": f"run not found: {run_id}"}
    found["status"] = status
    found["updated_at"] = _now()
    if status in ("done", "cancelled", "blocked"):
        found["completed_at"] = _now()
    if note:
        found.setdefault("notes", []).append(note)
    data["last_run_by_op"][found["op_id"]] = {
        "run_id": run_id,
        "at": found["updated_at"],
        "dry_run": found.get("dry_run"),
        "status": status,
    }
    _save(data, base_dir)
    return {"ok": True, "run": found}


def list_op_runs(
    *,
    op_id: str | None = None,
    status: str = "all",
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    out = []
    for r in _load(base_dir).get("runs") or []:
        if op_id and r.get("op_id") != op_id:
            continue
        if status and status != "all" and r.get("status") != status:
            continue
        out.append(r)
    return out[: max(1, int(limit or 50))]


def last_runs(base_dir: Path | None = None) -> dict[str, Any]:
    return dict(_load(base_dir).get("last_run_by_op") or {})


def scheduled_ops_status(
    *,
    risk_tolerance: str = "medium",
    base_dir: Path | None = None,
    include_budget: bool = True,
) -> dict[str, Any]:
    """Summary for autonomy/status surfaces.

    When include_budget is True, attach #634 remaining_tokens from durable snapshot
    so operators see whether apply runs would gate on budget.
    """
    rank = {"off": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    tol = rank.get((risk_tolerance or "medium").lower(), 0)
    runnable = []
    gated = []
    for o in OPS_CATALOG:
        item = {
            "id": o["id"],
            "cadence": o["cadence"],
            "risk_level": o["risk_level"],
            "requires_human": o["requires_human"],
            "estimated_tokens_dry_run": estimate_op_cost(o["id"], dry_run=True).get(
                "estimated_tokens"
            ),
            "estimated_tokens_apply": estimate_op_cost(o["id"], dry_run=False).get(
                "estimated_tokens"
            ),
        }
        if rank.get(str(o["risk_level"]).lower(), 2) <= tol and not o["requires_human"]:
            runnable.append(item)
        else:
            gated.append(item)
    out: dict[str, Any] = {
        "ops": list_ops(),
        "runnable_at_tolerance": runnable,
        "gated": gated,
        "last_run_by_op": last_runs(base_dir),
        "risk_tolerance": risk_tolerance,
        "n_ops": len(OPS_CATALOG),
    }
    if include_budget:
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot()
            out["budget_remaining_tokens"] = snap.get("remaining_tokens")
            out["budget_pressure"] = snap.get("budget_pressure")
            out["would_pause_next_cycle"] = snap.get("would_pause_next_cycle")
        except Exception as exc:
            out["budget_error"] = str(exc)
    return out


def ops_feed_items(
    *,
    risk_tolerance: str = "medium",
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Feed: only active/blocked scheduled op *runs* (not the full gated catalog)."""
    items = []
    for r in list_op_runs(status="all", limit=limit * 2, base_dir=base_dir):
        if r.get("status") not in ("blocked", "running", "planned"):
            continue
        oid = r.get("op_id")
        full = get_op(str(oid)) or {"id": oid, "description": oid, "risk_level": "medium"}
        items.append(
            {
                "id": r.get("id") or f"sop-{oid}",
                "item_type": "scheduled_op",
                "title": f"Scheduled op [{r.get('status')}]: {oid}",
                "op_id": oid,
                "risk_level": full.get("risk_level"),
                "badges": ["scheduled_op", str(r.get("status")), str(full.get("risk_level") or "medium")],
                "source": "scheduled_ops",
                "impact": "high" if full.get("risk_level") in ("high", "critical") else "medium",
                "reason": full.get("description") or str(oid),
                "ask_user_question": build_op_packet(full, dry_run=True).get("ask_user_question"),
            }
        )
        if len(items) >= limit:
            break
    return items


def run_procedure_dispatch(
    proc_id: str,
    *,
    dry_run: bool = True,
    risk_tolerance: str = "medium",
    approved: bool = False,
    checkpoint_id: str | None = None,
    base_dir: Path | None = None,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
) -> dict[str, Any] | None:
    """If proc_id is a #641 op, run it; else return None for caller fallback."""
    if get_op(proc_id) is None:
        return None
    return run_scheduled_op(
        proc_id,
        dry_run=dry_run,
        risk_tolerance=risk_tolerance,
        approved=approved,
        checkpoint_id=checkpoint_id,
        base_dir=base_dir,
        budget_remaining=budget_remaining,
        use_live_budget=use_live_budget,
    )
