"""Autonomous bug resolution loop orchestration (#638).

State machine that drives end-to-end bug fix work:
  plan → open_pr_draft → add_failing_test → implement_fix → ready_for_review
  → babysit → human_checkpoint? → merge_eligible → done

Durable runs under .agentic/bug_loops/. Does not silently merge or force-push;
emits agent packets + gate checks. Integrates babysit, collab, shadow, checkpoints.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUG_LOOP_DIR = Path(".agentic/bug_loops")
RUNS_FILE = "runs.json"
MARKER_BEGIN = "<!-- PLATE-BUG-LOOP:BEGIN -->"
MARKER_END = "<!-- PLATE-BUG-LOOP:END -->"

STAGES = (
    "plan",
    "open_pr_draft",
    "add_failing_test",
    "implement_fix",
    "ready_for_review",
    "babysit",
    "human_checkpoint",
    "merge_eligible",
    "done",
    "blocked",
    "cancelled",
)

# Stage → agent packet prompt
STAGE_PROMPTS: dict[str, str] = {
    "plan": (
        "Reproduce or document reproduction; confirm Bug issue labels; "
        "run gh plate release status; plan TDD fix on feature/bug branch from origin/release."
    ),
    "open_pr_draft": (
        "Open draft PR targeting release (legacy) with Bug label + Closes #N in body only; "
        "clean human title; branch bug/<issue>-short-slug."
    ),
    "add_failing_test": (
        "Add failing regression test that reproduces the bug (TDD). Push to PR branch."
    ),
    "implement_fix": (
        "Implement minimal fix; run targeted tests; push until green locally."
    ),
    "ready_for_review": (
        "Mark PR ready (gh pr ready); ensure labels, fragment if process, CI started."
    ),
    "babysit": (
        "CI diagnosis first; gh plate pr babysit N --act; resolve threads; fix gates until CLEAN."
    ),
    "human_checkpoint": (
        "High-risk or need:human-review: open #648 checkpoint / feed Task; wait for approve."
    ),
    "merge_eligible": (
        "All agent gates green; report merge readiness. Do not self-merge unless autonomy allows."
    ),
    "done": "Bug loop complete; post USAGE REPORT on issue if closing.",
}


@dataclass
class BugLoopRun:
    """One autonomous bug resolution run."""

    id: str
    bug_number: int | None
    bug_title: str
    stage: str = "plan"
    status: str = "active"  # active | done | blocked | cancelled
    pr_number: int | None = None
    branch: str | None = None
    risk: str = "medium"
    size: str = "medium"
    cost_estimate_tokens: int | None = None
    requires_human: bool = False
    checkpoint_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BugLoopRun":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or BUG_LOOP_DIR
    if d.name == RUNS_FILE:
        return d
    return d / RUNS_FILE


def _load(base: Path | None = None) -> dict[str, Any]:
    path = _store_path(base)
    if not path.exists():
        return {"version": 1, "runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "runs": []}
        data.setdefault("version", 1)
        data.setdefault("runs", [])
        if not isinstance(data["runs"], list):
            data["runs"] = []
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "runs": []}


def _save(data: dict[str, Any], base: Path | None = None) -> Path:
    path = _store_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def render_bug_loop_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def next_stage(current: str, *, skip_checkpoint: bool = False) -> str:
    order = [
        "plan",
        "open_pr_draft",
        "add_failing_test",
        "implement_fix",
        "ready_for_review",
        "babysit",
        "human_checkpoint",
        "merge_eligible",
        "done",
    ]
    if current not in order:
        return "plan"
    i = order.index(current)
    nxt = order[min(i + 1, len(order) - 1)]
    if skip_checkpoint and nxt == "human_checkpoint":
        return "merge_eligible"
    return nxt


def assess_human_required(
    *,
    risk: str = "medium",
    labels: list[str] | None = None,
    risk_tolerance: str = "medium",
    paths: list[str] | None = None,
) -> dict[str, Any]:
    """Decide if loop must pause at human_checkpoint."""
    labs = {str(x).lower() for x in (labels or [])}
    reasons: list[str] = []
    required = False
    if "need:human-review" in labs or "need:security-review" in labs:
        required = True
        reasons.append("need:human-review or security-review")
    if risk in ("high", "critical"):
        required = True
        reasons.append(f"bug risk={risk}")
    if (risk_tolerance or "").lower() == "off":
        required = True
        reasons.append("risk_tolerance=off")
    if (risk_tolerance or "").lower() == "low" and risk not in ("low",):
        required = True
        reasons.append("risk exceeds low tolerance")
    # High-risk paths
    high_paths = ("agents.md", ".github/workflows", "spec.md", ".plate")
    for p in paths or []:
        pl = str(p).lower().replace("\\", "/")
        if any(h in pl for h in high_paths):
            required = True
            reasons.append(f"high-risk path: {p}")
    return {"required": required, "reasons": reasons}


def stage_packet(run: dict[str, Any]) -> dict[str, Any]:
    """Build agent work packet for current stage."""
    stage = str(run.get("stage") or "plan")
    bug = run.get("bug_number")
    pr = run.get("pr_number")
    title = run.get("bug_title") or "bug"
    prompt = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["plan"])
    steps: list[str] = [prompt]
    if stage == "open_pr_draft" and bug:
        steps.append(f"Body must include Closes #{bug}")
        steps.append(f"Suggested branch: bug/{bug}-short-slug")
    if stage == "babysit" and pr:
        steps.append(f"gh plate pr babysit {pr} --act")
        steps.append(f"plate_get_pr_merge_gates pr_number={pr}")
    cid = run.get("checkpoint_id")
    if stage == "human_checkpoint":
        if cid:
            steps.append(f"plate_checkpoint_decide id={cid} decision=approve (or reject/revise)")
            steps.append(f"gh plate checkpoint --decide {cid} --decision approve")
            steps.append("Do not merge until checkpoint is approved; then plate_bug_loop_advance")
        else:
            steps.append("plate_bug_loop_advance opens #648 checkpoint; decide then re-advance")
    if stage == "merge_eligible" and pr:
        steps.append(f"Report merge readiness for PR #{pr}; human merges when risk-off")
    options: list[dict[str, str]]
    if stage == "human_checkpoint" and cid:
        options = [
            {
                "id": "approve",
                "label": "Approve checkpoint",
                "description": f"plate_checkpoint_decide {cid} approve then advance",
            },
            {
                "id": "reject",
                "label": "Reject",
                "description": f"plate_checkpoint_decide {cid} reject",
            },
            {
                "id": "cancel",
                "label": "Cancel loop",
                "description": f"plate_bug_loop_cancel {run.get('id')}",
            },
        ]
        question = (
            f"Approve bug loop checkpoint {cid} for #{bug or '?'} "
            f"({str(title)[:60]}) before merge?"
        )
    else:
        options = [
            {"id": "advance", "label": "Advance stage", "description": f"plate_bug_loop_advance {run.get('id')}"},
            {"id": "block", "label": "Mark blocked", "description": "Need more info / human"},
            {"id": "cancel", "label": "Cancel loop", "description": f"plate_bug_loop_cancel {run.get('id')}"},
        ]
        question = f"Bug loop [{stage}] for #{bug or '?'}: {str(title)[:80]} — advance?"
    return {
        "run_id": run.get("id"),
        "stage": stage,
        "bug_number": bug,
        "pr_number": pr,
        "branch": run.get("branch"),
        "title": title,
        "checkpoint_id": cid,
        "prompt": prompt,
        "steps": steps,
        "ask_user_question": {
            "question": question,
            "options": options,
        },
        "marker": render_bug_loop_marker(
            {"id": run.get("id"), "stage": stage, "bug": bug, "pr": pr, "checkpoint_id": cid}
        ),
    }


def estimate_bug_cost(
    *,
    size: str = "medium",
    needs_repro: bool = True,
    e2e: bool = False,
) -> dict[str, Any]:
    """Upfront cost estimate for a Bug loop (#638/#634 parity with feature)."""
    bases = {
        "trivial": 1500,
        "small": 2500,
        "medium": 4000,
        "large": 7000,
    }
    size_key = (size or "medium").lower()
    if size_key not in bases:
        size_key = "medium"
    tokens = bases[size_key]
    if needs_repro:
        tokens += 800
    if e2e:
        tokens += 1500
    return {
        "size": size_key,
        "estimated_tokens": tokens,
        "needs_repro": needs_repro,
        "e2e": e2e,
        "note": "Estimate is advisory; AutonomyEngine budget still enforces hard ceilings.",
    }


def start_bug_loop(
    *,
    bug_number: int | None = None,
    bug_title: str = "",
    risk: str = "medium",
    size: str = "medium",
    labels: list[str] | None = None,
    paths: list[str] | None = None,
    risk_tolerance: str = "medium",
    pr_number: int | None = None,
    branch: str | None = None,
    needs_repro: bool = True,
    e2e: bool = False,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
    budget_base_dir: Path | None = None,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Start a durable bug resolution run at plan (or babysit if PR already exists).

    When ``budget_remaining`` is omitted and ``use_live_budget`` is True (default),
    hydrate remaining tokens from durable #634 budget snapshot (same rails as feature_loop).
    """
    title = (bug_title or "").strip() or (f"Bug #{bug_number}" if bug_number else "Untitled bug")
    est = estimate_bug_cost(size=size, needs_repro=needs_repro, e2e=e2e)
    human = assess_human_required(
        risk=risk, labels=labels, risk_tolerance=risk_tolerance, paths=paths
    )
    blocked = False
    notes = list(human.get("reasons") or [])
    budget_snap: dict[str, Any] | None = None
    effective_budget = budget_remaining
    if effective_budget is None and use_live_budget:
        try:
            from .autonomy import get_budget_snapshot

            budget_snap = get_budget_snapshot(
                estimated_tokens=int(est["estimated_tokens"]),
                base_dir=budget_base_dir,
            )
            # Honor durable remaining even when risk_tolerance=off (engine disabled).
            # risk-off only skips AutonomyEngine cycles; surface gates still apply (#634).
            if budget_snap.get("remaining_tokens") is not None:
                effective_budget = int(budget_snap.get("remaining_tokens") or 0)
                notes.append(
                    f"budget hydrated: remaining_tokens={effective_budget} "
                    f"pressure={budget_snap.get('budget_pressure')} "
                    f"enabled={budget_snap.get('enabled')}"
                )
                if budget_snap.get("would_pause") or budget_snap.get("would_throttle"):
                    blocked = True
                    notes.append(
                        budget_snap.get("gate_reason")
                        or "blocked: live budget estimate gate"
                    )
        except Exception as exc:
            notes.append(f"budget hydrate skipped: {exc}")

    if (
        not blocked
        and effective_budget is not None
        and est["estimated_tokens"] > effective_budget
    ):
        blocked = True
        notes.append(
            f"blocked: est {est['estimated_tokens']} > budget remaining {effective_budget}"
        )

    ts = _now()
    stage = "plan"
    if pr_number:
        stage = "babysit"
    run = BugLoopRun(
        id=f"bugloop-{uuid.uuid4().hex[:10]}",
        bug_number=bug_number,
        bug_title=title,
        stage=stage,
        status="blocked" if blocked else "active",
        pr_number=pr_number,
        branch=branch or (f"bug/{bug_number}-fix" if bug_number else None),
        risk=(risk or "medium").lower(),
        size=est["size"],
        cost_estimate_tokens=est["estimated_tokens"],
        requires_human=bool(human["required"]),
        history=[{"ts": ts, "stage": stage, "event": "started", "estimate": est}],
        notes=notes,
        created_at=ts,
        updated_at=ts,
        metadata={
            "labels": list(labels or []),
            "paths": list(paths or []),
            "risk_tolerance": risk_tolerance,
            "estimate": est,
            "budget_remaining": effective_budget,
            "budget_source": (
                "explicit"
                if budget_remaining is not None
                else (
                    "live"
                    if budget_snap is not None
                    and budget_snap.get("remaining_tokens") is not None
                    else "none"
                )
            ),
        },
    )
    data = _load(base_dir)
    data["runs"].append(run.to_dict())
    _save(data, base_dir)
    out: dict[str, Any] = {
        "ok": not blocked,
        "run": run.to_dict(),
        "packet": stage_packet(run.to_dict()),
        "human_assessment": human,
        "estimate": est,
        "blocked": blocked,
        "budget_remaining": effective_budget,
    }
    if budget_snap is not None:
        out["budget_snapshot"] = budget_snap
    if blocked:
        out["error"] = notes[-1] if notes else "budget blocked"
    elif use_live_budget:
        try:
            from .autonomy import apply_live_budget_charge

            out.setdefault("notes", list(notes))
            apply_live_budget_charge(
                out,
                tokens=int(est["estimated_tokens"] or 0),
                use_live_budget=True,
                action_kind="bug_loop_start",
                reason=f"start_bug_loop:{run.id}",
                base_dir=budget_base_dir,
            )
        except Exception:
            pass
    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="bug_loop_start",
                decision="pause" if blocked else "proceed",
                reason=(
                    f"start bug loop for #{bug_number}: {title[:80]}"
                    if not blocked
                    else f"budget blocked bug loop #{bug_number}: {notes[-1] if notes else 'budget'}"
                ),
                sources=["bug_loop", "#638", "#634"],
                risk_tolerance=risk_tolerance,
                impact=risk,
                related_issue=bug_number,
                related_pr=pr_number,
                actor="bug_loop",
                cost_estimate_tokens=est["estimated_tokens"],
                metadata={"run_id": run.id, "blocked": blocked},
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass
    return out


def get_bug_loop(run_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for r in _load(base_dir).get("runs") or []:
        if r.get("id") == run_id:
            return r
        if run_id.isdigit() and r.get("bug_number") == int(run_id) and r.get("status") == "active":
            return r
    return None


def list_bug_loops(
    *,
    status: str = "active",
    limit: int = 50,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    out = []
    for r in _load(base_dir).get("runs") or []:
        if status and status != "all" and r.get("status") != status:
            continue
        out.append(r)
    return out[: max(1, int(limit or 50))]


def update_bug_loop(
    run_id: str,
    *,
    stage: str | None = None,
    status: str | None = None,
    pr_number: int | None = None,
    branch: str | None = None,
    note: str | None = None,
    checkpoint_id: str | None = None,
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
    if stage:
        if stage not in STAGES:
            return {"ok": False, "error": f"invalid stage: {stage}"}
        found["stage"] = stage
        found.setdefault("history", []).append(
            {"ts": _now(), "stage": stage, "event": "set_stage"}
        )
    if status:
        found["status"] = status
    if pr_number is not None:
        found["pr_number"] = pr_number
    if branch is not None:
        found["branch"] = branch
    if checkpoint_id is not None:
        found["checkpoint_id"] = checkpoint_id
    if note:
        found.setdefault("notes", []).append(note)
    found["updated_at"] = _now()
    _save(data, base_dir)
    return {"ok": True, "run": found, "packet": stage_packet(found)}


def _checkpoint_base(base_dir: Path | None) -> Path | None:
    """Isolate checkpoints under loop base_dir in tests; production uses default."""
    if base_dir is None:
        return None
    return Path(base_dir) / "checkpoints"


def _open_human_checkpoint_for_run(found: dict[str, Any], *, base_dir: Path | None) -> dict[str, Any] | None:
    """Create a durable #648 checkpoint when entering human_checkpoint (once)."""
    if found.get("checkpoint_id"):
        return None
    try:
        from .checkpoint import create_checkpoint
    except Exception:
        return None
    bug_n = found.get("bug_number")
    title = f"Approve bug loop merge: {found.get('bug_title') or bug_n or found.get('id')}"
    reason = (
        f"Bug loop #{bug_n or '?'} at human_checkpoint "
        f"(risk={found.get('risk')}; pr={found.get('pr_number')}). "
        "Approve before merge_eligible."
    )
    cp = create_checkpoint(
        title=title[:200],
        reason=reason,
        impact="high" if str(found.get("risk") or "").lower() in ("high", "critical") else "medium",
        action_kind="bug_loop_merge",
        scope={
            "run_id": found.get("id"),
            "loop": "bug",
            "stage": "human_checkpoint",
        },
        related_issue=int(bug_n) if bug_n is not None else None,
        related_pr=int(found["pr_number"]) if found.get("pr_number") is not None else None,
        created_by="bug_loop",
        risk_tolerance="off",
        autonomy_enabled=False,
        pause_autonomy=True,
        base_dir=_checkpoint_base(base_dir),
    )
    if isinstance(cp, dict) and cp.get("id"):
        found["checkpoint_id"] = cp["id"]
        found.setdefault("notes", []).append(f"opened checkpoint {cp['id']}")
        found.setdefault("history", []).append(
            {"ts": _now(), "stage": "human_checkpoint", "event": "checkpoint_opened", "checkpoint_id": cp["id"]}
        )
        return cp
    return None


def _human_checkpoint_blocks_advance(
    found: dict[str, Any],
    *,
    force_skip_checkpoint: bool,
    base_dir: Path | None,
) -> dict[str, Any] | None:
    """If at human_checkpoint without approved #648, return a blocked advance payload."""
    if force_skip_checkpoint:
        return None
    cid = found.get("checkpoint_id")
    if not cid:
        # Ensure a checkpoint exists before leaving this stage
        _open_human_checkpoint_for_run(found, base_dir=base_dir)
        cid = found.get("checkpoint_id")
    if not cid:
        return {
            "ok": True,
            "advanced": False,
            "reason": "human_checkpoint requires a #648 checkpoint_id",
            "run": found,
            "packet": stage_packet(found),
        }
    try:
        from .checkpoint import checkpoint_approval_for_gate
    except Exception as exc:
        return {
            "ok": True,
            "advanced": False,
            "reason": f"checkpoint module unavailable: {exc}",
            "run": found,
            "packet": stage_packet(found),
        }
    gate = checkpoint_approval_for_gate(
        str(cid),
        action_kind="bug_loop_merge",
        base_dir=_checkpoint_base(base_dir),
    )
    if gate.get("approved"):
        return None
    return {
        "ok": True,
        "advanced": False,
        "reason": gate.get("reason")
        or f"checkpoint {cid} not approved; stay on human_checkpoint",
        "checkpoint_id": cid,
        "checkpoint_gate": gate,
        "run": found,
        "packet": stage_packet(found),
    }


def advance_bug_loop(
    run_id: str,
    *,
    pr_number: int | None = None,
    branch: str | None = None,
    note: str | None = None,
    force_skip_checkpoint: bool = False,
    base_dir: Path | None = None,
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance one stage with optional gate checks at babysit/merge."""
    data = _load(base_dir)
    found = None
    for r in data["runs"]:
        if r.get("id") == run_id:
            found = r
            break
    if not found:
        return {"ok": False, "error": f"run not found: {run_id}"}
    if found.get("status") not in ("active",):
        return {"ok": False, "error": f"run not active: {found.get('status')}", "run": found}

    if pr_number is not None:
        found["pr_number"] = pr_number
    if branch is not None:
        found["branch"] = branch
    if note:
        found.setdefault("notes", []).append(note)

    cur = str(found.get("stage") or "plan")
    # Gate: cannot leave babysit / merge_eligible if gates say not clean (when provided)
    if cur in ("babysit", "merge_eligible") and gates is not None:
        from .pr_babysit import evaluate_babysit_gates

        gate = evaluate_babysit_gates(gates)
        if gate.get("blocked"):
            reason = str(gate.get("reason") or "gates not clean")
            found.setdefault("notes", []).append(f"babysit gate: {reason}")
            found["updated_at"] = _now()
            found["last_gate_checks"] = gate.get("checks") or {}
            _save(data, base_dir)
            return {
                "ok": True,
                "advanced": False,
                "reason": reason,
                "gate_checks": gate.get("checks"),
                "run": found,
                "packet": stage_packet(found),
            }

    # #648: cannot leave human_checkpoint without approved checkpoint
    if cur == "human_checkpoint":
        blocked = _human_checkpoint_blocks_advance(
            found, force_skip_checkpoint=force_skip_checkpoint, base_dir=base_dir
        )
        if blocked is not None:
            found["updated_at"] = _now()
            _save(data, base_dir)
            blocked["run"] = found
            blocked["packet"] = stage_packet(found)
            return blocked

    skip_cp = force_skip_checkpoint or not found.get("requires_human")
    # When leaving babysit, go to human_checkpoint if required
    if cur == "babysit" and found.get("requires_human") and not force_skip_checkpoint:
        nxt = "human_checkpoint"
    else:
        nxt = next_stage(cur, skip_checkpoint=skip_cp)

    opened_cp = None
    if nxt == "human_checkpoint":
        opened_cp = _open_human_checkpoint_for_run(found, base_dir=base_dir)

    found["stage"] = nxt
    if nxt == "done":
        found["status"] = "done"
    found.setdefault("history", []).append(
        {"ts": _now(), "stage": nxt, "event": "advanced", "from": cur}
    )
    found["updated_at"] = _now()
    _save(data, base_dir)
    out: dict[str, Any] = {
        "ok": True,
        "advanced": True,
        "from_stage": cur,
        "to_stage": nxt,
        "run": found,
        "packet": stage_packet(found),
    }
    if opened_cp is not None:
        out["checkpoint"] = opened_cp
        out["checkpoint_id"] = opened_cp.get("id")
    elif found.get("checkpoint_id"):
        out["checkpoint_id"] = found.get("checkpoint_id")
    return out


def run_bug_loop_tick(
    run_id: str,
    *,
    dry_run: bool = True,
    base_dir: Path | None = None,
    fetch_gates: bool = False,
    repo: str | None = None,
) -> dict[str, Any]:
    """One orchestrator tick: emit packet; optionally fetch merge gates on babysit.

    dry_run=True: never advances stage automatically (report only).
    dry_run=False: advances when safe (e.g. after babysit CLEAN).
    """
    run = get_bug_loop(run_id, base_dir=base_dir)
    if not run:
        return {"ok": False, "error": f"run not found: {run_id}"}
    packet = stage_packet(run)
    gates = None
    if run.get("stage") == "babysit" and run.get("pr_number") and fetch_gates:
        try:
            from .pr_babysit import get_pr_merge_gates

            gates = get_pr_merge_gates(int(run["pr_number"]), repo=repo)
            packet["gates"] = {
                "merge_state": gates.get("merge_state"),
                "unresolved_review_threads": gates.get("unresolved_review_threads"),
                "actionable_agent_threads": gates.get("actionable_agent_threads"),
                "review_decision": gates.get("review_decision"),
                "ci_state": gates.get("ci_state"),
                "ci_failing": gates.get("ci_failing"),
                "ci_pending": gates.get("ci_pending"),
                "failing_checks": gates.get("failing_checks"),
                "pending_checks": gates.get("pending_checks"),
                "loop_advance_blocked": gates.get("loop_advance_blocked"),
                "loop_advance_reason": gates.get("loop_advance_reason"),
            }
        except Exception as exc:
            packet["gates_error"] = str(exc)

    result: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "run": run,
        "packet": packet,
    }
    if not dry_run and run.get("stage") == "babysit" and gates:
        adv = advance_bug_loop(run_id, gates=gates, base_dir=base_dir)
        result["advance"] = adv
        result["run"] = adv.get("run") or run
        result["packet"] = adv.get("packet") or packet
    return result


def cancel_bug_loop(run_id: str, *, note: str = "", base_dir: Path | None = None) -> dict[str, Any]:
    return update_bug_loop(run_id, status="cancelled", stage="cancelled", note=note or "cancelled", base_dir=base_dir)


def bug_loop_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    items = []
    for r in list_bug_loops(status="active", limit=limit, base_dir=base_dir):
        pkt = stage_packet(r)
        items.append(
            {
                "id": r.get("id"),
                "item_type": "bug_loop",
                "title": f"Bug loop [{r.get('stage')}]: {r.get('bug_title')}",
                "stage": r.get("stage"),
                "bug_number": r.get("bug_number"),
                "pr_number": r.get("pr_number"),
                "cost_estimate_tokens": r.get("cost_estimate_tokens"),
                "requires_human": r.get("requires_human"),
                "badges": ["bug_loop", str(r.get("stage")), str(r.get("risk"))],
                "source": "bug_loop",
                "impact": "high" if r.get("requires_human") else "medium",
                "reason": pkt.get("prompt"),
                "ask_user_question": pkt.get("ask_user_question"),
                "marker": pkt.get("marker"),
            }
        )
    return items
