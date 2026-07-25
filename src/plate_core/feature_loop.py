"""Autonomous feature implementation loop orchestration (#639).

State machine for end-to-end Feature work:
  estimate_cost → plan → open_pr_draft → add_failing_tests → implement
  → docs_fragment → media_capture → ready_for_review → babysit
  → human_checkpoint? → merge_eligible → done

Durable runs under .agentic/feature_loops/. Emits agent packets; no silent merge.
Integrates babysit, cost estimate, design-validation hooks, media approval.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEATURE_LOOP_DIR = Path(".agentic/feature_loops")
RUNS_FILE = "runs.json"
MARKER_BEGIN = "<!-- PLATE-FEATURE-LOOP:BEGIN -->"
MARKER_END = "<!-- PLATE-FEATURE-LOOP:END -->"

STAGES = (
    "estimate_cost",
    "plan",
    "open_pr_draft",
    "add_failing_tests",
    "implement",
    "docs_fragment",
    "media_capture",
    "ready_for_review",
    "babysit",
    "human_checkpoint",
    "merge_eligible",
    "done",
    "blocked",
    "cancelled",
)

STAGE_PROMPTS: dict[str, str] = {
    "estimate_cost": (
        "Estimate tokens/USD for the Feature (tests + impl + docs + babysit). "
        "Record estimate; gate on budget remaining / cost_ceiling."
    ),
    "plan": (
        "Confirm ACs, tests plan, design-validation needs (#646), fragment slug; "
        "run gh plate release status; plan branch feature/<issue>-slug from origin/release."
    ),
    "open_pr_draft": (
        "Open draft PR targeting release with Feature label + Closes #N in body only; "
        "clean human title; unreleased fragment path noted."
    ),
    "add_failing_tests": (
        "Add failing unit tests + design/visual contract tests where applicable (TDD first)."
    ),
    "implement": (
        "Implement minimal Feature to green targeted tests in isolated worktree; push."
    ),
    "docs_fragment": (
        "Author .agentic/releases/unreleased/<slug>.json; update wiki/docs if process-facing."
    ),
    "media_capture": (
        "Plan+record explanatory GIF via plate_feature_media_plan + record_e2e_gif (#636); "
        "register, user-approve, attach to fragment media[] (#635); or skip with reason."
    ),
    "ready_for_review": (
        "gh pr ready; ensure labels, feature-change-files, CI started."
    ),
    "babysit": (
        "CI diagnosis first; gh plate pr babysit N --act; resolve threads; gates until CLEAN."
    ),
    "human_checkpoint": (
        "Media/design/public-claim approval via #648 checkpoint or feed; wait for approve."
    ),
    "merge_eligible": (
        "Agent gates green; report merge readiness. Do not self-merge unless autonomy allows."
    ),
    "done": "Feature loop complete; USAGE REPORT on issue if closing.",
}

# Rough token bases by stage residual (for estimate_cost)
_ESTIMATE_BASE = {
    "trivial": 4000,
    "small": 8000,
    "medium": 18000,
    "large": 35000,
}


@dataclass
class FeatureLoopRun:
    id: str
    feature_number: int | None
    feature_title: str
    stage: str = "estimate_cost"
    status: str = "active"
    pr_number: int | None = None
    branch: str | None = None
    risk: str = "medium"
    size: str = "medium"  # trivial|small|medium|large
    cost_estimate_tokens: int | None = None
    requires_human: bool = False
    needs_media_approval: bool = True
    needs_design_validation: bool = False
    checkpoint_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureLoopRun":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path(base: Path | None = None) -> Path:
    d = base or FEATURE_LOOP_DIR
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


def render_feature_loop_marker(payload: dict[str, Any]) -> str:
    return f"{MARKER_BEGIN}\n{json.dumps(payload, indent=2)}\n{MARKER_END}\n"


def estimate_feature_cost(
    *,
    size: str = "medium",
    needs_design_validation: bool = False,
    needs_media: bool = True,
    e2e: bool = False,
) -> dict[str, Any]:
    """Upfront cost estimate for a Feature loop (#639)."""
    size_n = (size or "medium").lower()
    if size_n not in _ESTIMATE_BASE:
        size_n = "medium"
    tokens = _ESTIMATE_BASE[size_n]
    if needs_design_validation:
        tokens += 3000
    if needs_media:
        tokens += 2000
    if e2e:
        tokens += 5000
    return {
        "size": size_n,
        "estimated_tokens": tokens,
        "breakdown": {
            "base": _ESTIMATE_BASE[size_n],
            "design_validation": 3000 if needs_design_validation else 0,
            "media": 2000 if needs_media else 0,
            "e2e": 5000 if e2e else 0,
        },
        "notes": [
            "Estimate is advisory; AutonomyEngine budget still enforces hard ceilings.",
            "Shadow high-impact work via plate_autonomy_simulate when impact high/critical.",
        ],
    }


def next_stage(
    current: str,
    *,
    skip_checkpoint: bool = False,
    skip_media: bool = False,
) -> str:
    order = [
        "estimate_cost",
        "plan",
        "open_pr_draft",
        "add_failing_tests",
        "implement",
        "docs_fragment",
        "media_capture",
        "ready_for_review",
        "babysit",
        "human_checkpoint",
        "merge_eligible",
        "done",
    ]
    if current not in order:
        return "estimate_cost"
    i = order.index(current)
    nxt = order[min(i + 1, len(order) - 1)]
    if skip_media and nxt == "media_capture":
        nxt = order[order.index("media_capture") + 1]
    if skip_checkpoint and nxt == "human_checkpoint":
        return "merge_eligible"
    return nxt


def assess_human_required(
    *,
    risk: str = "medium",
    labels: list[str] | None = None,
    risk_tolerance: str = "medium",
    needs_media_approval: bool = True,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    labs = {str(x).lower() for x in (labels or [])}
    reasons: list[str] = []
    required = False
    if "need:human-review" in labs or "need:security-review" in labs:
        required = True
        reasons.append("need:human-review or security-review")
    if risk in ("high", "critical"):
        required = True
        reasons.append(f"feature risk={risk}")
    if (risk_tolerance or "").lower() == "off":
        required = True
        reasons.append("risk_tolerance=off")
    if (risk_tolerance or "").lower() == "low" and risk not in ("low",):
        required = True
        reasons.append("risk exceeds low tolerance")
    if needs_media_approval:
        # media approval is a soft human gate — still route through checkpoint stage
        reasons.append("media/GIF approval expected")
        # only force required if risk not low or tolerance low
        if risk != "low" or (risk_tolerance or "").lower() in ("off", "low"):
            required = True
    high_paths = ("agents.md", ".github/workflows", "spec.md", ".plate", "readme.md")
    for p in paths or []:
        pl = str(p).lower().replace("\\", "/")
        if any(h in pl for h in high_paths):
            required = True
            reasons.append(f"high-risk path: {p}")
    return {"required": required, "reasons": reasons}


def stage_packet(run: dict[str, Any]) -> dict[str, Any]:
    stage = str(run.get("stage") or "estimate_cost")
    feat = run.get("feature_number")
    pr = run.get("pr_number")
    title = run.get("feature_title") or "feature"
    prompt = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["plan"])
    steps: list[str] = [prompt]
    if stage == "estimate_cost":
        steps.append(
            f"Recorded estimate: {run.get('cost_estimate_tokens')} tokens (size={run.get('size')})"
        )
    if stage == "open_pr_draft" and feat:
        steps.append(f"Body must include Closes #{feat}")
        steps.append(f"Suggested branch: feature/{feat}-short-slug")
    if stage == "docs_fragment":
        steps.append("Fragment under .agentic/releases/unreleased/<slug>.json required for Feature PRs")
    if stage == "media_capture":
        steps.append(
            f"plate_feature_media_plan feature_number={feat} title={title!r} then record_e2e_gif"
        )
        steps.append("plate_feature_media_register + decide approve; attach_fragment to unreleased slug")
    if stage == "babysit" and pr:
        steps.append(f"gh plate pr babysit {pr} --act")
        steps.append(f"plate_get_pr_merge_gates pr_number={pr}")
    cid = run.get("checkpoint_id")
    if stage == "human_checkpoint":
        if cid:
            steps.append(f"plate_checkpoint_decide id={cid} decision=approve (or reject/revise)")
            steps.append(f"gh plate checkpoint --decide {cid} --decision approve")
            steps.append("Do not merge until checkpoint is approved; then plate_feature_loop_advance")
        else:
            steps.append("plate_feature_loop_advance opens #648 checkpoint; decide then re-advance")
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
                "description": f"plate_feature_loop_cancel {run.get('id')}",
            },
        ]
        question = (
            f"Approve feature loop checkpoint {cid} for #{feat or '?'} "
            f"({str(title)[:60]}) before merge?"
        )
    else:
        options = [
            {
                "id": "advance",
                "label": "Advance stage",
                "description": f"plate_feature_loop_advance {run.get('id')}",
            },
            {
                "id": "block",
                "label": "Mark blocked",
                "description": "Need more info / budget / human",
            },
            {
                "id": "cancel",
                "label": "Cancel loop",
                "description": f"plate_feature_loop_cancel {run.get('id')}",
            },
        ]
        question = f"Feature loop [{stage}] for #{feat or '?'}: {str(title)[:80]} — advance?"
    return {
        "run_id": run.get("id"),
        "stage": stage,
        "feature_number": feat,
        "pr_number": pr,
        "branch": run.get("branch"),
        "title": title,
        "checkpoint_id": cid,
        "cost_estimate_tokens": run.get("cost_estimate_tokens"),
        "prompt": prompt,
        "steps": steps,
        "ask_user_question": {
            "question": question,
            "options": options,
        },
        "marker": render_feature_loop_marker(
            {"id": run.get("id"), "stage": stage, "feature": feat, "pr": pr, "checkpoint_id": cid}
        ),
    }


def start_feature_loop(
    *,
    feature_number: int | None = None,
    feature_title: str = "",
    risk: str = "medium",
    size: str = "medium",
    labels: list[str] | None = None,
    paths: list[str] | None = None,
    risk_tolerance: str = "medium",
    needs_design_validation: bool = False,
    needs_media_approval: bool = True,
    e2e: bool = False,
    pr_number: int | None = None,
    branch: str | None = None,
    budget_remaining: int | None = None,
    use_live_budget: bool = True,
    budget_base_dir: Path | None = None,
    base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Start a durable Feature implementation run.

    When ``budget_remaining`` is omitted and ``use_live_budget`` is True (default),
    hydrate remaining tokens from durable #634 budget snapshot so starts honor the
    same rails as AutonomyEngine without a manual CLI flag.
    """
    title = (feature_title or "").strip() or (
        f"Feature #{feature_number}" if feature_number else "Untitled feature"
    )
    est = estimate_feature_cost(
        size=size,
        needs_design_validation=needs_design_validation,
        needs_media=needs_media_approval,
        e2e=e2e,
    )
    human = assess_human_required(
        risk=risk,
        labels=labels,
        risk_tolerance=risk_tolerance,
        needs_media_approval=needs_media_approval,
        paths=paths,
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
            # Only enforce live rails when autonomy is enabled (risk != off)
            if budget_snap.get("enabled"):
                effective_budget = int(budget_snap.get("remaining_tokens") or 0)
                notes.append(
                    f"budget hydrated: remaining_tokens={effective_budget} "
                    f"pressure={budget_snap.get('budget_pressure')}"
                )
                if budget_snap.get("would_pause") or budget_snap.get("would_throttle"):
                    # Mirror engine: pause/throttle both block start of large Features
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
    stage = "estimate_cost"
    if pr_number:
        stage = "babysit"
    run = FeatureLoopRun(
        id=f"featloop-{uuid.uuid4().hex[:10]}",
        feature_number=feature_number,
        feature_title=title,
        stage=stage,
        status="blocked" if blocked else "active",
        pr_number=pr_number,
        branch=branch or (f"feature/{feature_number}-impl" if feature_number else None),
        risk=(risk or "medium").lower(),
        size=est["size"],
        cost_estimate_tokens=est["estimated_tokens"],
        requires_human=bool(human["required"]),
        needs_media_approval=needs_media_approval,
        needs_design_validation=needs_design_validation,
        history=[{"ts": ts, "stage": stage, "event": "started", "estimate": est}],
        notes=notes,
        created_at=ts,
        updated_at=ts,
        metadata={
            "labels": list(labels or []),
            "paths": list(paths or []),
            "risk_tolerance": risk_tolerance,
            "estimate": est,
            "e2e": e2e,
            "budget_remaining": effective_budget,
            "budget_source": (
                "explicit"
                if budget_remaining is not None
                else ("live" if budget_snap and budget_snap.get("enabled") else "none")
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
        "estimate": est,
        "human_assessment": human,
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
                action_kind="feature_loop_start",
                reason=f"start_feature_loop:{run.id}",
                base_dir=budget_base_dir,
            )
        except Exception:
            pass
    if record_ledger:
        try:
            from .ledger import record_decision

            rec = record_decision(
                action_kind="feature_loop_start",
                decision="pause" if blocked else "proceed",
                reason=f"start feature loop for #{feature_number}: {title[:80]}",
                sources=["feature_loop", "#639", "#634"],
                risk_tolerance=risk_tolerance,
                impact=risk,
                related_issue=feature_number,
                related_pr=pr_number,
                cost_estimate_tokens=est["estimated_tokens"],
                actor="feature_loop",
                metadata={"run_id": run.id},
            )
            out["ledger_id"] = rec.get("id") if isinstance(rec, dict) else None
        except Exception:
            pass
    return out


def get_feature_loop(run_id: str, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    for r in _load(base_dir).get("runs") or []:
        if r.get("id") == run_id:
            return r
        if run_id.isdigit() and r.get("feature_number") == int(run_id) and r.get("status") == "active":
            return r
    return None


def list_feature_loops(
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


def update_feature_loop(
    run_id: str,
    *,
    stage: str | None = None,
    status: str | None = None,
    pr_number: int | None = None,
    branch: str | None = None,
    note: str | None = None,
    checkpoint_id: str | None = None,
    cost_estimate_tokens: int | None = None,
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
    if cost_estimate_tokens is not None:
        found["cost_estimate_tokens"] = cost_estimate_tokens
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
    feat_n = found.get("feature_number")
    title = f"Approve feature loop: {found.get('feature_title') or feat_n or found.get('id')}"
    reason = (
        f"Feature loop #{feat_n or '?'} at human_checkpoint "
        f"(risk={found.get('risk')}; pr={found.get('pr_number')}; "
        f"media={found.get('needs_media_approval')}). Approve before merge_eligible."
    )
    impact = "high" if str(found.get("risk") or "").lower() in ("high", "critical") else "medium"
    cp = create_checkpoint(
        title=title[:200],
        reason=reason,
        impact=impact,
        action_kind="feature_loop_merge",
        scope={
            "run_id": found.get("id"),
            "loop": "feature",
            "stage": "human_checkpoint",
            "cost_estimate_tokens": found.get("cost_estimate_tokens"),
        },
        related_issue=int(feat_n) if feat_n is not None else None,
        related_pr=int(found["pr_number"]) if found.get("pr_number") is not None else None,
        created_by="feature_loop",
        risk_tolerance="off",
        autonomy_enabled=False,
        pause_autonomy=True,
        base_dir=_checkpoint_base(base_dir),
    )
    if isinstance(cp, dict) and cp.get("id"):
        found["checkpoint_id"] = cp["id"]
        found.setdefault("notes", []).append(f"opened checkpoint {cp['id']}")
        found.setdefault("history", []).append(
            {
                "ts": _now(),
                "stage": "human_checkpoint",
                "event": "checkpoint_opened",
                "checkpoint_id": cp["id"],
            }
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
        action_kind="feature_loop_merge",
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


def advance_feature_loop(
    run_id: str,
    *,
    pr_number: int | None = None,
    branch: str | None = None,
    note: str | None = None,
    force_skip_checkpoint: bool = False,
    skip_media: bool = False,
    base_dir: Path | None = None,
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    cur = str(found.get("stage") or "estimate_cost")
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
    skip_m = skip_media or not found.get("needs_media_approval")
    if cur == "babysit" and found.get("requires_human") and not force_skip_checkpoint:
        nxt = "human_checkpoint"
    else:
        nxt = next_stage(cur, skip_checkpoint=skip_cp, skip_media=skip_m)

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


def run_feature_loop_tick(
    run_id: str,
    *,
    dry_run: bool = True,
    base_dir: Path | None = None,
    fetch_gates: bool = False,
    repo: str | None = None,
) -> dict[str, Any]:
    run = get_feature_loop(run_id, base_dir=base_dir)
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
    if not dry_run:
        stage = str(run.get("stage") or "")
        # estimate_cost is recorded at start; auto-advance so PM ticks make progress (#639/#660)
        if stage == "estimate_cost":
            adv = advance_feature_loop(
                run_id,
                skip_media=not bool(run.get("needs_media_approval")),
                base_dir=base_dir,
            )
            result["advance"] = adv
            result["run"] = adv.get("run") or run
            result["packet"] = adv.get("packet") or packet
        elif stage == "babysit" and gates:
            adv = advance_feature_loop(run_id, gates=gates, base_dir=base_dir)
            result["advance"] = adv
            result["run"] = adv.get("run") or run
            result["packet"] = adv.get("packet") or packet
    return result


def cancel_feature_loop(
    run_id: str, *, note: str = "", base_dir: Path | None = None
) -> dict[str, Any]:
    return update_feature_loop(
        run_id,
        status="cancelled",
        stage="cancelled",
        note=note or "cancelled",
        base_dir=base_dir,
    )


def feature_loop_feed_items(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    items = []
    for r in list_feature_loops(status="active", limit=limit, base_dir=base_dir):
        pkt = stage_packet(r)
        items.append(
            {
                "id": r.get("id"),
                "item_type": "feature_loop",
                "title": f"Feature loop [{r.get('stage')}]: {r.get('feature_title')}",
                "stage": r.get("stage"),
                "feature_number": r.get("feature_number"),
                "pr_number": r.get("pr_number"),
                "cost_estimate_tokens": r.get("cost_estimate_tokens"),
                "requires_human": r.get("requires_human"),
                "badges": ["feature_loop", str(r.get("stage")), str(r.get("risk"))],
                "source": "feature_loop",
                "impact": "high" if r.get("requires_human") else "medium",
                "reason": pkt.get("prompt"),
                "ask_user_question": pkt.get("ask_user_question"),
                "marker": pkt.get("marker"),
            }
        )
    return items
