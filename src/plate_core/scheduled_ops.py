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
        "description": "Package for marketplace; real publish is human Task (#380/#381/#626)",
        "requires_human": True,
        "impact": "critical",
        "steps": [
            "Build package artifacts locally",
            "Detect human blockers: plate_task_detect marketplace/PyPI",
            "Do NOT publish secrets; open Task issues for human publish",
            "Document package paths for human owner",
        ],
        "tools": ["plate_task_detect", "plate_task_create"],
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
    return {"ok": True, "op": op, "packet": build_op_packet(op, dry_run=dry_run)}


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
) -> dict[str, Any]:
    """Start/record a scheduled op run. dry_run default — no side effects beyond local ledger."""
    op = get_op(op_id)
    if not op:
        return {"ok": False, "error": f"unknown op: {op_id}"}

    risk = str(op.get("risk_level") or "medium")
    needs_human = bool(op.get("requires_human")) or risk in ("high", "critical")
    rank = {"off": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    tol = rank.get((risk_tolerance or "medium").lower(), 0)
    op_rank = rank.get(risk.lower(), 2)

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

    packet = build_op_packet(op, dry_run=dry_run)
    ts = _now()
    run = ScheduledOpRun(
        id=f"sop-{uuid.uuid4().hex[:10]}",
        op_id=op_id,
        status="blocked" if blocked else ("done" if dry_run else "running"),
        dry_run=dry_run,
        requires_human=needs_human,
        checkpoint_id=checkpoint_id,
        packet=packet,
        notes=reasons + ([note] if note else []),
        created_at=ts,
        updated_at=ts,
        completed_at=ts if (dry_run and not blocked) else None,
        metadata={"risk_tolerance": risk_tolerance, "approved": approved},
    )
    if dry_run and not blocked:
        run.notes.append("dry_run complete: packet emitted; no remote side effects")
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
        "log_marker": (
            f"<!-- PLATE-PROCEDURE-RUN:{op_id} cadence={op.get('cadence')} "
            f"risk={risk} dry_run={dry_run} -->"
        ),
    }
    if blocked:
        out["error"] = "; ".join(reasons)
        out["reason"] = out["error"]

    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="scheduled_op",
                decision="pause" if blocked else ("proceed" if not dry_run else "shadow"),
                reason=f"scheduled op {op_id}: {out.get('status')}",
                sources=["scheduled_ops", "#641"],
                risk_tolerance=risk_tolerance,
                impact=risk,
                checkpoint_id=checkpoint_id,
                actor="scheduled_ops",
                metadata={"run_id": run.id, "op_id": op_id, "dry_run": dry_run},
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
) -> dict[str, Any]:
    """Summary for autonomy/status surfaces."""
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
        }
        if rank.get(str(o["risk_level"]).lower(), 2) <= tol and not o["requires_human"]:
            runnable.append(item)
        else:
            gated.append(item)
    return {
        "ops": list_ops(),
        "runnable_at_tolerance": runnable,
        "gated": gated,
        "last_run_by_op": last_runs(base_dir),
        "risk_tolerance": risk_tolerance,
        "n_ops": len(OPS_CATALOG),
    }


def ops_feed_items(
    *,
    risk_tolerance: str = "medium",
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Feed: ops that need human attention or are due (manual cadence always listed if gated)."""
    st = scheduled_ops_status(risk_tolerance=risk_tolerance, base_dir=base_dir)
    items = []
    for o in st["gated"][:limit]:
        full = get_op(o["id"]) or o
        items.append(
            {
                "id": f"sop-{o['id']}",
                "item_type": "scheduled_op",
                "title": f"Scheduled op needs gate: {o['id']}",
                "op_id": o["id"],
                "risk_level": o.get("risk_level"),
                "badges": ["scheduled_op", o.get("risk_level") or "medium", "gated"],
                "source": "scheduled_ops",
                "impact": "high" if o.get("risk_level") in ("high", "critical") else "medium",
                "reason": full.get("description") or o["id"],
                "ask_user_question": build_op_packet(full, dry_run=True).get("ask_user_question"),
            }
        )
    return items


def run_procedure_dispatch(
    proc_id: str,
    *,
    dry_run: bool = True,
    risk_tolerance: str = "medium",
    approved: bool = False,
    checkpoint_id: str | None = None,
    base_dir: Path | None = None,
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
    )
