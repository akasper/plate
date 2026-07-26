"""Project Manager / Orchestrator core (#660).

Long-running coordination loop: poll what_next + feed signals, assign work to
specialized personas within budget, surface checkpoints, and emit quiet cycle
reports. GitHub remains source of truth; this module holds ephemeral runtime
queue state and durable markers under .agentic/pm/.

Slices:
- v1 (#660 first): team catalog, assign_work, run_cycle, MCP/CLI
- v2 (orchestrator loop deepen): durable assignment queue, checkpoint module
  open-count, ledger provenance on cycles, complete_assignment, multi-cycle
  run_loop, ask_user_question payloads on assignment presentation, high-impact
  assignments open #648 checkpoints before execute
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PM_DIR = Path(".agentic/pm")
QUEUE_FILE = "queue.json"
LAST_CYCLE_FILE = "last_cycle.json"
MARKER_BEGIN = "<!-- PLATE-PM-CYCLE:BEGIN -->"
MARKER_END = "<!-- PLATE-PM-CYCLE:END -->"

# Pre-defined sub-agent personas (initial team for #660)
TEAM: list[dict[str, Any]] = [
    {
        "id": "dev-cautious",
        "role": "developer",
        "name": "Cautious Implementer",
        "style": "TDD-first, high coverage, risk-averse",
        "skills": ["implement", "test", "bugfix"],
        "risk_bias": "low",
    },
    {
        "id": "dev-pragmatic",
        "role": "developer",
        "name": "Pragmatic Hacker",
        "style": "Fast MVP, working code first",
        "skills": ["implement", "prototype", "bugfix"],
        "risk_bias": "medium",
    },
    {
        "id": "dev-refactorer",
        "role": "developer",
        "name": "Refactorer",
        "style": "Clean architecture, rearch, debt paydown",
        "skills": ["refactor", "architecture", "implement"],
        "risk_bias": "medium",
    },
    {
        "id": "design-minimal",
        "role": "designer",
        "name": "Minimalist",
        "style": "Clean accessible UI",
        "skills": ["design", "wireframe", "a11y"],
        "risk_bias": "low",
    },
    {
        "id": "design-storyteller",
        "role": "designer",
        "name": "Creative Storyteller",
        "style": "Rich visuals, marketing, GIFs",
        "skills": ["design", "media", "marketing"],
        "risk_bias": "medium",
    },
    {
        "id": "research-analyst",
        "role": "researcher",
        "name": "Research Analyst",
        "style": "Evidence synthesis, market scans",
        "skills": ["research", "docs", "audit"],
        "risk_bias": "low",
    },
    {
        "id": "release-engineer",
        "role": "release",
        "name": "Release Engineer",
        "style": "Ceremony, packaging, tags",
        "skills": ["release", "packaging", "docs"],
        "risk_bias": "low",
    },
    {
        "id": "pm-orchestrator",
        "role": "pm",
        "name": "PM Orchestrator",
        "style": "Coordination, budgeting, handoffs",
        "skills": ["orchestrate", "budget", "checkpoint"],
        "risk_bias": "medium",
    },
]


@dataclass
class Assignment:
    assignment_id: str
    work_id: str
    work_title: str
    work_type: str
    agent_id: str
    agent_name: str
    rationale: str
    estimated_tokens: int
    requires_checkpoint: bool = False
    status: str = "proposed"  # proposed | delegated | blocked | done | cancelled
    packet: dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PMStatus:
    enabled: bool = True
    risk_tolerance: str = "off"
    budget_remaining_tokens: int | None = None
    burn_rate: float = 0.0
    autopilot_score: int = 0
    team_size: int = 0
    open_assignments: int = 0
    open_checkpoints: int = 0
    last_cycle: str | None = None
    queue_size: int = 0
    proposed: int = 0
    delegated: int = 0
    blocked: int = 0
    done: int = 0
    # #660 harden: cost dashboard / durable budget gates
    budget_pressure: str = "ok"  # ok | elevated | critical | exhausted
    would_pause_next_cycle: bool = False
    spent_today_durable: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_pm_dir(base: Path | None = None) -> Path:
    d = base or PM_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_team() -> list[dict[str, Any]]:
    return list(TEAM)


def get_persona(agent_id: str) -> dict[str, Any] | None:
    for p in TEAM:
        if p["id"] == agent_id:
            return dict(p)
    return None


def classify_work_type(item: dict[str, Any]) -> str:
    """Map feed/what_next item to work type for assignment."""
    t = str(item.get("item_type") or item.get("type") or item.get("kind") or "").lower()
    title = str(item.get("title") or item.get("next_action") or "").lower()
    if t in ("task", "checkpoint") or "checkpoint" in title:
        return "checkpoint"
    if t == "question" or "question" in title:
        return "qanda"
    if "design" in title or t == "design":
        return "design"
    if "research" in title or t == "research":
        return "research"
    if "release" in title or "cut" in title or "finalize" in title:
        return "release"
    if "bug" in title or "fix" in title:
        return "bugfix"
    if "refactor" in title or "rearch" in title:
        return "refactor"
    return "implement"


def estimate_assignment_tokens(work_type: str) -> int:
    bases = {
        "qanda": 1500,
        "design": 4000,
        "research": 5000,
        "implement": 6000,
        "bugfix": 3500,
        "refactor": 5500,
        "release": 7000,
        "checkpoint": 800,
    }
    return bases.get(work_type, 3000)


def pick_agent(work_type: str, risk_tolerance: str = "medium") -> dict[str, Any]:
    """Choose persona by skill match + risk bias."""
    skill_map = {
        "qanda": "docs",
        "design": "design",
        "research": "research",
        "implement": "implement",
        "bugfix": "bugfix",
        "refactor": "refactor",
        "release": "release",
        "checkpoint": "checkpoint",
    }
    want = skill_map.get(work_type, "implement")
    risk_rank = {"off": 0, "low": 1, "medium": 2, "high": 3}
    tol = risk_rank.get((risk_tolerance or "medium").lower(), 2)

    candidates = []
    for p in TEAM:
        if p["role"] == "pm":
            continue
        skills = p.get("skills") or []
        if want not in skills and work_type not in ("qanda",):
            # soft match: researchers handle qanda
            if work_type == "qanda" and "docs" in skills:
                pass
            elif work_type == "qanda" and p["role"] == "researcher":
                pass
            else:
                if want not in skills:
                    continue
        bias = risk_rank.get(str(p.get("risk_bias") or "medium"), 2)
        # prefer agents whose bias <= tolerance
        score = 10 if want in skills else 5
        if bias <= tol:
            score += 3
        if work_type == "refactor" and p["id"] == "dev-refactorer":
            score += 5
        if work_type == "implement" and p["id"] == "dev-cautious" and tol <= 1:
            score += 4
        if work_type == "implement" and p["id"] == "dev-pragmatic" and tol >= 2:
            score += 4
        candidates.append((score, p))
    if not candidates:
        # fallback cautious dev
        return dict(TEAM[0])
    candidates.sort(key=lambda x: (-x[0], x[1]["id"]))
    return dict(candidates[0][1])


def build_assignment_tui(assignment: dict[str, Any]) -> dict[str, Any]:
    """ask_user_question-shaped payload for host TUI on one assignment."""
    aid = assignment.get("assignment_id") or "asg"
    title = assignment.get("work_title") or "work"
    agent = assignment.get("agent_name") or assignment.get("agent_id") or "agent"
    status = assignment.get("status") or "proposed"
    return {
        "question": f"PM assignment [{status}]: {title} → {agent}?",
        "options": [
            {
                "label": "Approve & run (Recommended)",
                "description": f"Proceed with {agent} for this packet",
            },
            {
                "label": "Reassign",
                "description": "Pick a different persona",
            },
            {
                "label": "Defer",
                "description": "Leave proposed; revisit next cycle",
            },
            {
                "label": "Cancel",
                "description": "Mark assignment cancelled",
            },
        ],
        "multi_select": False,
        "assignment_id": aid,
        "host_hint": "Present via ask_user_question; call plate_pm_complete after run.",
    }


def _issue_number_from_assignment(asg: dict[str, Any]) -> int | None:
    """Best-effort GitHub issue number for loop start from assignment/work fields."""
    for key in ("work_number", "issue_number", "number", "feature_number", "bug_number"):
        raw = asg.get(key)
        if raw is None and isinstance(asg.get("packet"), dict):
            raw = asg["packet"].get(key)
        if raw is None and isinstance(asg.get("item"), dict):
            raw = asg["item"].get(key) or asg["item"].get("number")
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    wid = str(asg.get("work_id") or "")
    if wid.isdigit():
        return int(wid)
    # e.g. "issue-123" or "#42"
    m = re.search(r"(?:#|issue[-_]?|feature[-_]?|bug[-_]?)(\d+)", wid, re.I)
    if m:
        return int(m.group(1))
    return None


def dispatch_loop_from_assignment(
    asg: dict[str, Any],
    *,
    budget_remaining: int | None = None,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
    artifact_base_dir: Path | None = None,
    budget_base_dir: Path | None = None,
    record_ledger: bool = True,
) -> dict[str, Any]:
    """Open durable #638/#639 loop or #632 artifact from a delegated PM assignment (#660 bridge).

    - work_type ``implement`` / feature-like → ``start_feature_loop`` (live budget hydrate)
    - work_type ``bugfix`` → ``start_bug_loop``
    - work_type ``design`` / ``research`` → ``propose_artifact`` (#632 pending approval)
    Other types are skipped (release/qanda stay as packets/fleet only).
    Never merges; loops emit agent packets only; artifacts stay pending until human decide.
    """
    work_type = str(asg.get("work_type") or "").lower()
    title = str(asg.get("work_title") or asg.get("title") or "PM work")
    risk = str(asg.get("risk") or asg.get("impact") or "medium").lower()
    if risk in ("critical",):
        risk = "high"
    risk_tol = str(
        asg.get("risk_tolerance")
        or (asg.get("packet") or {}).get("risk_tolerance")
        or "medium"
    )
    labels = list(asg.get("labels") or (asg.get("packet") or {}).get("labels") or [])
    issue_n = _issue_number_from_assignment(asg)

    if work_type in ("implement", "feature", "refactor"):
        from .feature_loop import start_feature_loop

        size = "medium"
        if work_type == "refactor":
            size = "large"
        out = start_feature_loop(
            feature_number=issue_n,
            feature_title=title,
            risk=risk if risk in ("low", "medium", "high") else "medium",
            size=size,
            labels=labels or None,
            risk_tolerance=risk_tol,
            needs_media_approval=False,
            budget_remaining=budget_remaining,
            use_live_budget=budget_remaining is None,
            budget_base_dir=budget_base_dir,
            base_dir=feature_loop_base_dir,
            record_ledger=record_ledger,
        )
        run = out.get("run") or {}
        return {
            "ok": bool(out.get("ok")),
            "loop_kind": "feature",
            "run_id": run.get("id"),
            "stage": run.get("stage"),
            "blocked": bool(out.get("blocked")),
            "error": out.get("error"),
            "budget_remaining": out.get("budget_remaining"),
            "result": out,
        }

    if work_type in ("bugfix", "bug"):
        from .bug_loop import start_bug_loop

        out = start_bug_loop(
            bug_number=issue_n,
            bug_title=title,
            risk=risk if risk in ("low", "medium", "high") else "medium",
            labels=labels or None,
            risk_tolerance=risk_tol,
            budget_remaining=budget_remaining,
            use_live_budget=budget_remaining is None,
            budget_base_dir=budget_base_dir,
            base_dir=bug_loop_base_dir,
            record_ledger=record_ledger,
        )
        run = out.get("run") or {}
        return {
            "ok": bool(out.get("ok", True)),
            "loop_kind": "bug",
            "run_id": run.get("id"),
            "stage": run.get("stage"),
            "blocked": bool(out.get("blocked")),
            "error": out.get("error"),
            "budget_remaining": out.get("budget_remaining"),
            "result": out,
        }

    if work_type in ("design", "research"):
        from .design_research_approval import propose_artifact

        packet = asg.get("packet") if isinstance(asg.get("packet"), dict) else {}
        summary = str(
            asg.get("summary")
            or packet.get("summary")
            or packet.get("prompt_segment")
            or f"PM-proposed {work_type} for approval: {title}"
        )[:2000]
        content_path = str(
            asg.get("content_path") or packet.get("content_path") or ""
        )
        content_excerpt = str(
            asg.get("content_excerpt") or packet.get("content_excerpt") or ""
        )[:2000]
        out = propose_artifact(
            work_type,
            title,
            summary,
            content_path=content_path,
            content_excerpt=content_excerpt,
            related_issue=issue_n,
            actor="pm",
            base_dir=artifact_base_dir,
            budget_remaining=budget_remaining,
            use_live_budget=budget_remaining is None,
        )
        if out.get("blocked") or out.get("reason") == "budget":
            return {
                "ok": False,
                "loop_kind": "artifact",
                "run_id": out.get("id"),
                "stage": "blocked",
                "blocked": True,
                "error": out.get("error") or out.get("reason") or "budget",
                "budget_remaining": out.get("budget_remaining"),
                "result": out,
            }
        if record_ledger:
            _ledger_pm(
                "pm_dispatch_artifact",
                "proposed",
                f"PM proposed {work_type} artifact for #{issue_n or 'n/a'}: {title[:80]}",
                cost=out.get("cost_estimate_tokens"),
                risk=risk_tol,
                impact=risk,
                metadata={
                    "proposal_id": out.get("id"),
                    "work_type": work_type,
                    "assignment_id": asg.get("assignment_id"),
                },
            )
        return {
            "ok": bool(out.get("ok", True)),
            "loop_kind": "artifact",
            "run_id": out.get("id"),
            "stage": out.get("status") or "pending",
            "blocked": False,
            "error": out.get("error"),
            "budget_remaining": out.get("budget_remaining"),
            "ask_user_question": out.get("ask_user_question"),
            "result": out,
        }

    return {
        "ok": False,
        "skipped": True,
        "reason": f"work_type={work_type} has no bug/feature/artifact mapping",
        "loop_kind": None,
    }


def assign_work(
    item: dict[str, Any],
    *,
    risk_tolerance: str = "medium",
    budget_remaining: int | None = None,
    open_checkpoint: bool = False,
    checkpoint_base_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a budget-aware assignment packet for one work item."""
    work_type = classify_work_type(item)
    est = estimate_assignment_tokens(work_type)
    impact = str(item.get("impact") or "medium").lower()
    requires_cp = work_type in ("release", "checkpoint") or impact in ("high", "critical")
    agent = pick_agent(work_type, risk_tolerance)
    ts = _now()

    blocked = False
    reason_parts = [f"matched skill for {work_type} → {agent['id']}"]
    if budget_remaining is not None and est > budget_remaining:
        blocked = True
        reason_parts.append(f"blocked: est {est} > budget remaining {budget_remaining}")
    if risk_tolerance == "off" and work_type not in ("qanda", "checkpoint"):
        blocked = True
        reason_parts.append("blocked: risk_tolerance=off")

    work_number = item.get("number") or item.get("issue_number") or item.get("feature_number") or item.get("bug_number")
    try:
        work_number_int = int(work_number) if work_number is not None else None
    except (TypeError, ValueError):
        work_number_int = None
    assignment = Assignment(
        assignment_id=f"asg-{uuid.uuid4().hex[:10]}",
        work_id=str(item.get("id") or item.get("number") or item.get("title") or "work"),
        work_title=str(item.get("title") or item.get("next_action") or "untitled"),
        work_type=work_type,
        agent_id=agent["id"],
        agent_name=agent["name"],
        rationale="; ".join(reason_parts),
        estimated_tokens=est,
        requires_checkpoint=requires_cp,
        status="blocked" if blocked else "proposed",
        packet={
            "agent_id": agent["id"],
            "persona": agent,
            "task_summary": str(item.get("title") or item.get("next_action") or ""),
            "prompt_segment": item.get("prompt_segment")
            or f"Execute {work_type} for: {item.get('title')}. Follow TDD, quiet ops, Closes in PR body.",
            "impact": impact,
            "risk_tolerance": risk_tolerance,
            "number": work_number_int,
            "issue_number": work_number_int,
            "labels": list(item.get("labels") or []) or None,
            "source_item": {
                k: item[k]
                for k in item
                if k in ("id", "number", "url", "item_type", "type", "reason")
            },
        },
        created_at=ts,
        updated_at=ts,
    )
    if requires_cp and not blocked:
        assignment.status = "proposed"
        assignment.rationale += "; high-impact: surface checkpoint before execute"
        if open_checkpoint:
            try:
                from .checkpoint import create_checkpoint

                cp = create_checkpoint(
                    title=f"PM approve: {assignment.work_title[:80]}",
                    reason=f"High-impact {work_type} assignment to {agent['id']}",
                    impact=impact if impact in ("high", "critical") else "medium",
                    action_kind=f"pm_assign_{work_type}",
                    scope={
                        "assignment_id": assignment.assignment_id,
                        "agent_id": agent["id"],
                        "work_type": work_type,
                    },
                    risk_tolerance=risk_tolerance,
                    autonomy_enabled=risk_tolerance not in ("off",),
                    created_by="pm",
                    base_dir=checkpoint_base_dir,
                )
                assignment.checkpoint_id = cp.get("id")
                assignment.packet["checkpoint_id"] = cp.get("id")
                assignment.rationale += f"; checkpoint={cp.get('id')}"
            except Exception as exc:  # pragma: no cover - best effort
                assignment.rationale += f"; checkpoint_open_failed={exc}"

    out = assignment.to_dict()
    if work_number_int is not None:
        out["work_number"] = work_number_int
        out["number"] = work_number_int
    out["risk_tolerance"] = risk_tolerance
    out["ask_user_question"] = build_assignment_tui(out)
    return out


def _count_open_checkpoints(checkpoint_base_dir: Path | None = None) -> int:
    """Count pending #648 checkpoints that pause unsupervised cycles.

    Uses ``list_open_checkpoints`` (filters ``pause_autonomy``) so advisory
    shadow-gate records under risk=off do not freeze PM forever (#645/#648/#660).
    """
    try:
        from .checkpoint import list_open_checkpoints

        rows = list_open_checkpoints(base_dir=checkpoint_base_dir, limit=100)
        return len(rows)
    except Exception:
        return 0


def _ledger_pm(
    action_kind: str,
    decision: str,
    reason: str,
    *,
    cost: int | None = None,
    risk: str = "",
    impact: str = "",
    checkpoint_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        from .ledger import record_decision

        record_decision(
            action_kind=action_kind,
            decision=decision,
            reason=reason,
            sources=["pm", "#660"],
            cost_estimate_tokens=cost,
            risk_tolerance=risk,
            impact=impact,
            checkpoint_id=checkpoint_id,
            actor="pm",
            metadata=metadata or {},
        )
    except Exception:
        pass


class ProjectManager:
    """Budget-aware orchestrator cycle runner with durable assignment queue."""

    def __init__(
        self,
        repo: str | None = None,
        state_dir: Path | None = None,
        checkpoint_base_dir: Path | None = None,
        fleet_base_dir: Path | None = None,
        feature_loop_base_dir: Path | None = None,
        bug_loop_base_dir: Path | None = None,
        artifact_base_dir: Path | None = None,
        budget_base_dir: Path | None = None,
        dispatch_fleet: bool = True,
        dispatch_loops: bool = True,
    ):
        self.repo = repo
        self.state_dir = state_dir
        self.checkpoint_base_dir = checkpoint_base_dir
        self.fleet_base_dir = fleet_base_dir
        self.feature_loop_base_dir = feature_loop_base_dir
        self.bug_loop_base_dir = bug_loop_base_dir
        self.artifact_base_dir = artifact_base_dir
        self.budget_base_dir = budget_base_dir
        self.dispatch_fleet = dispatch_fleet
        self.dispatch_loops = dispatch_loops
        self._assignments: list[dict[str, Any]] = self._load_queue()

    def _queue_path(self) -> Path:
        return _ensure_pm_dir(self.state_dir) / QUEUE_FILE

    def _load_queue(self) -> list[dict[str, Any]]:
        path = _ensure_pm_dir(self.state_dir) / QUEUE_FILE
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rows = data.get("assignments") or []
            elif isinstance(data, list):
                rows = data
            else:
                rows = []
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            return []

    def _save_queue(self) -> None:
        path = self._queue_path()
        path.write_text(
            json.dumps(
                {
                    "updated_at": _now(),
                    "assignments": self._assignments,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def list_queue(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List durable queue entries; optionally filter by status."""
        rows = list(self._assignments)
        if status and status != "all":
            rows = [r for r in rows if r.get("status") == status]
        out = []
        for r in rows[:limit]:
            item = dict(r)
            if "ask_user_question" not in item:
                item["ask_user_question"] = build_assignment_tui(item)
            out.append(item)
        return out

    def promote_checkpoint_ready_assignments(
        self,
        *,
        dry_run: bool = True,
        dispatch_fleet: bool | None = None,
        dispatch_loops: bool | None = None,
        budget_remaining: int | None = None,
    ) -> list[dict[str, Any]]:
        """Promote proposed high-impact assignments after #648 checkpoint approve (#885).

        When ``run_cycle`` opens a checkpoint for high-impact work it leaves the
        assignment ``proposed``. After the human approves the checkpoint, the next
        PM cycle must promote to ``delegated`` and run fleet/loop dispatch — this
        was previously a no-op comment only.
        """
        do_fleet = self.dispatch_fleet if dispatch_fleet is None else bool(dispatch_fleet)
        do_loops = self.dispatch_loops if dispatch_loops is None else bool(dispatch_loops)
        results: list[dict[str, Any]] = []
        changed = False
        for asg in self._assignments:
            if asg.get("status") != "proposed":
                continue
            if not asg.get("requires_checkpoint"):
                continue
            cid = asg.get("checkpoint_id") or (asg.get("packet") or {}).get(
                "checkpoint_id"
            )
            if not cid:
                continue
            try:
                from .checkpoint import get_checkpoint

                cp = get_checkpoint(str(cid), base_dir=self.checkpoint_base_dir)
            except Exception as exc:
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "ok": False,
                        "error": f"checkpoint lookup failed: {exc}",
                    }
                )
                continue
            if not cp:
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "ok": False,
                        "error": f"checkpoint not found: {cid}",
                    }
                )
                continue
            cp_st = str(cp.get("status") or "").lower()
            if cp_st == "pending":
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "ok": True,
                        "action": "wait",
                        "checkpoint_id": cid,
                        "checkpoint_status": cp_st,
                    }
                )
                continue
            if cp_st in ("rejected", "cancelled"):
                if not dry_run:
                    asg["status"] = "cancelled" if cp_st == "cancelled" else "blocked"
                    asg["updated_at"] = _now()
                    asg.setdefault("packet", {})["checkpoint_decision"] = cp_st
                    changed = True
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "ok": True,
                        "action": "cancel" if cp_st == "cancelled" else "block",
                        "checkpoint_id": cid,
                        "checkpoint_status": cp_st,
                        "dry_run": dry_run,
                    }
                )
                continue
            if cp_st not in ("approved",):
                # revised etc. — keep proposed
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "ok": True,
                        "action": "hold",
                        "checkpoint_id": cid,
                        "checkpoint_status": cp_st,
                    }
                )
                continue

            # Approved → promote + dispatch (same as run_cycle delegated path)
            row: dict[str, Any] = {
                "assignment_id": asg.get("assignment_id"),
                "ok": True,
                "action": "promote",
                "checkpoint_id": cid,
                "checkpoint_status": cp_st,
                "dry_run": dry_run,
            }
            if dry_run:
                results.append(row)
                continue

            asg["status"] = "delegated"
            asg["updated_at"] = _now()
            asg.setdefault("packet", {})["checkpoint_decision"] = "approved"
            changed = True

            if do_fleet:
                try:
                    from .fleet import handoff_from_pm_assignment

                    ho = handoff_from_pm_assignment(
                        asg,
                        budget_remaining=budget_remaining,
                        open_checkpoint=False,
                        base_dir=self.fleet_base_dir,
                        record_ledger=True,
                    )
                    row["fleet"] = {
                        "ok": ho.get("ok"),
                        "handoff_id": (ho.get("handoff") or {}).get("handoff_id"),
                        "blocked": ho.get("blocked"),
                        "error": ho.get("error"),
                    }
                    if ho.get("ok"):
                        hid = (ho.get("handoff") or {}).get("handoff_id")
                        asg["fleet_handoff_id"] = hid
                        asg.setdefault("packet", {})["fleet_handoff_id"] = hid
                except Exception as exc:
                    row["fleet"] = {"ok": False, "error": str(exc)}

            if do_loops:
                try:
                    asg["risk_tolerance"] = asg.get("risk_tolerance") or (
                        asg.get("packet") or {}
                    ).get("risk_tolerance")
                    loop_out = dispatch_loop_from_assignment(
                        asg,
                        budget_remaining=budget_remaining,
                        feature_loop_base_dir=self.feature_loop_base_dir,
                        bug_loop_base_dir=self.bug_loop_base_dir,
                        artifact_base_dir=self.artifact_base_dir,
                        budget_base_dir=self.budget_base_dir,
                        record_ledger=True,
                    )
                    row["loop"] = {
                        "ok": loop_out.get("ok"),
                        "loop_kind": loop_out.get("loop_kind"),
                        "run_id": loop_out.get("run_id"),
                        "blocked": loop_out.get("blocked"),
                        "error": loop_out.get("error"),
                        "skipped": loop_out.get("skipped"),
                    }
                    if loop_out.get("ok") or loop_out.get("run_id"):
                        asg["loop_run_id"] = loop_out.get("run_id")
                        asg["loop_kind"] = loop_out.get("loop_kind")
                        asg.setdefault("packet", {})["loop_run_id"] = loop_out.get(
                            "run_id"
                        )
                        asg.setdefault("packet", {})["loop_kind"] = loop_out.get(
                            "loop_kind"
                        )
                except Exception as exc:
                    row["loop"] = {"ok": False, "error": str(exc)}

            _ledger_pm(
                "pm_promote_checkpoint",
                "proceed",
                f"promoted {asg.get('assignment_id')} after checkpoint {cid} approved",
                checkpoint_id=str(cid),
                metadata={
                    "assignment_id": asg.get("assignment_id"),
                    "work_type": asg.get("work_type"),
                },
            )
            results.append(row)

        if changed and not dry_run:
            self._save_queue()
        return results

    def complete_assignment(
        self,
        assignment_id: str,
        *,
        status: str = "done",
        note: str = "",
    ) -> dict[str, Any]:
        """Mark an assignment done/cancelled and persist queue."""
        allowed = {"done", "cancelled", "blocked", "proposed", "delegated"}
        st = (status or "done").lower()
        if st not in allowed:
            st = "done"
        found: dict[str, Any] | None = None
        for a in self._assignments:
            if a.get("assignment_id") == assignment_id or str(a.get("assignment_id", "")).startswith(
                assignment_id
            ):
                a["status"] = st
                a["updated_at"] = _now()
                if note:
                    a.setdefault("packet", {})["completion_note"] = note
                found = a
                break
        if not found:
            return {"ok": False, "error": f"assignment not found: {assignment_id}"}
        self._save_queue()
        _ledger_pm(
            "pm_complete_assignment",
            st,
            note or f"assignment {assignment_id} → {st}",
            metadata={"assignment_id": found.get("assignment_id"), "work_id": found.get("work_id")},
        )
        return {"ok": True, "assignment": found}

    def tick_delegated_loops(
        self,
        *,
        dry_run: bool = True,
        fetch_gates: bool = False,
        limit: int = 10,
        complete_when_done: bool = True,
    ) -> list[dict[str, Any]]:
        """Refresh #638/#639 loop and #632 artifact state for delegated PM assignments (#660 deepen).

        - Syncs ``loop_stage`` / packet from durable feature/bug loop runs
        - Syncs artifact proposal status (pending/approved/revise/reject)
        - On babysit + fetch_gates + not dry_run: may advance when gates clean
        - When loop reaches ``done`` or artifact is terminal, marks assignment done
        Does not invent git/PR work; agents still execute stage packets.
        """
        results: list[dict[str, Any]] = []
        changed = False
        n = 0
        for asg in self._assignments:
            if n >= limit:
                break
            if asg.get("status") not in ("delegated", "blocked"):
                continue
            rid = asg.get("loop_run_id") or (asg.get("packet") or {}).get("loop_run_id")
            kind = str(
                asg.get("loop_kind") or (asg.get("packet") or {}).get("loop_kind") or ""
            ).lower()
            if not rid or kind not in ("feature", "bug", "artifact"):
                continue
            n += 1

            # #632 artifact proposals: sync decide status; complete on terminal outcomes
            if kind == "artifact":
                try:
                    from .design_research_approval import get_proposal

                    prop = get_proposal(str(rid), base_dir=self.artifact_base_dir)
                except Exception as exc:
                    results.append(
                        {
                            "assignment_id": asg.get("assignment_id"),
                            "loop_run_id": rid,
                            "loop_kind": kind,
                            "ok": False,
                            "error": str(exc),
                        }
                    )
                    continue
                if not prop:
                    results.append(
                        {
                            "assignment_id": asg.get("assignment_id"),
                            "loop_run_id": rid,
                            "loop_kind": kind,
                            "ok": False,
                            "error": f"artifact proposal not found: {rid}",
                        }
                    )
                    continue
                stage = str(prop.get("status") or "pending")
                asg["loop_stage"] = stage
                asg.setdefault("packet", {})["loop_stage"] = stage
                asg.setdefault("packet", {})["loop_status"] = stage
                asg.setdefault("packet", {})["artifact_proposal_id"] = prop.get("id") or rid
                if prop.get("ask_user_question"):
                    asg.setdefault("packet", {})["artifact_ask_user_question"] = prop[
                        "ask_user_question"
                    ]
                completed = False
                terminal = stage in ("approved", "rejected", "reject", "cancelled")
                if complete_when_done and terminal:
                    asg["status"] = "done" if stage == "approved" else "cancelled"
                    if stage in ("rejected", "reject"):
                        asg["status"] = "cancelled"
                    asg["updated_at"] = _now()
                    asg.setdefault("packet", {})["completion_note"] = (
                        f"artifact {rid} → {stage}"
                    )
                    completed = True
                    changed = True
                else:
                    asg["updated_at"] = _now()
                    changed = True
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "loop_run_id": rid,
                        "loop_kind": kind,
                        "ok": True,
                        "stage": stage,
                        "run_status": stage,
                        "completed_assignment": completed,
                        "advanced": False,
                        "dry_run": dry_run,
                    }
                )
                continue

            tick: dict[str, Any]
            try:
                if kind == "feature":
                    from .feature_loop import run_feature_loop_tick

                    tick = run_feature_loop_tick(
                        str(rid),
                        dry_run=dry_run,
                        base_dir=self.feature_loop_base_dir,
                        fetch_gates=fetch_gates,
                        repo=self.repo,
                    )
                else:
                    from .bug_loop import run_bug_loop_tick

                    tick = run_bug_loop_tick(
                        str(rid),
                        dry_run=dry_run,
                        base_dir=self.bug_loop_base_dir,
                        fetch_gates=fetch_gates,
                        repo=self.repo,
                    )
            except Exception as exc:
                results.append(
                    {
                        "assignment_id": asg.get("assignment_id"),
                        "loop_run_id": rid,
                        "loop_kind": kind,
                        "ok": False,
                        "error": str(exc),
                    }
                )
                continue

            run = tick.get("run") or {}
            stage = run.get("stage")
            run_status = run.get("status")
            asg["loop_stage"] = stage
            asg.setdefault("packet", {})["loop_stage"] = stage
            asg.setdefault("packet", {})["loop_status"] = run_status
            if tick.get("packet"):
                asg.setdefault("packet", {})["loop_packet"] = {
                    k: tick["packet"].get(k)
                    for k in ("stage", "steps", "gates", "checkpoint_id", "prompt")
                    if k in (tick.get("packet") or {})
                }
            completed = False
            if complete_when_done and (
                run_status == "done" or stage == "done"
            ):
                asg["status"] = "done"
                asg["updated_at"] = _now()
                asg.setdefault("packet", {})["completion_note"] = (
                    f"loop {kind} {rid} reached done"
                )
                completed = True
                changed = True
            elif tick.get("advance") and (tick.get("advance") or {}).get("advanced"):
                changed = True
                asg["updated_at"] = _now()
            else:
                # always persist stage sync
                asg["updated_at"] = _now()
                changed = True

            row = {
                "assignment_id": asg.get("assignment_id"),
                "loop_run_id": rid,
                "loop_kind": kind,
                "ok": bool(tick.get("ok", True)),
                "stage": stage,
                "run_status": run_status,
                "completed_assignment": completed,
                "advanced": bool((tick.get("advance") or {}).get("advanced")),
                "dry_run": dry_run,
            }
            if tick.get("error"):
                row["error"] = tick.get("error")
            results.append(row)

        if changed:
            try:
                self._save_queue()
            except Exception:
                pass
        return results

    def get_status(self) -> PMStatus:
        auto: dict[str, Any] = {}
        # Prefer local .plate only when repo is unset to avoid offline/network hangs in tests.
        try:
            from .plate_config import load_plate_config

            conf = load_plate_config()
            acfg = (conf.to_dict() if hasattr(conf, "to_dict") else {}).get("autonomy") or {}
            auto = {
                "enabled": bool(acfg.get("enabled", False)),
                "risk_tolerance": str(acfg.get("risk_tolerance") or "off"),
                "budget_remaining_tokens": (acfg.get("token_budget") or {}).get("daily"),
                "burn_rate": 0.0,
                "autopilot_score": 0,
                "open_human_checkpoints": [],
            }
        except Exception:
            auto = {"enabled": False, "risk_tolerance": "off", "open_human_checkpoints": []}
        if self.repo:
            try:
                from .autonomy import get_autonomy_status

                live = get_autonomy_status(self.repo) or {}
                auto.update(live)
            except Exception:
                pass
        # Prefer durable #648 pending count; fall back to autonomy strings
        open_cp_count = _count_open_checkpoints(self.checkpoint_base_dir)
        if open_cp_count == 0:
            open_cp_count = len(list(auto.get("open_human_checkpoints") or []))

        by_status = {"proposed": 0, "delegated": 0, "blocked": 0, "done": 0, "cancelled": 0}
        for a in self._assignments:
            s = str(a.get("status") or "")
            if s in by_status:
                by_status[s] += 1

        last_cycle = None
        try:
            lc = _ensure_pm_dir(self.state_dir) / LAST_CYCLE_FILE
            if lc.exists():
                data = json.loads(lc.read_text(encoding="utf-8"))
                last_cycle = data.get("timestamp")
        except Exception:
            pass

        remaining = auto.get("budget_remaining_tokens")
        pressure = "ok"
        would_pause = False
        spent_durable: int | None = None
        # Durable spend first (no network) so PM honors #634 rails offline.
        # Must use get_budget_snapshot (UTC day rollover) — raw load_budget_spend
        # keeps prior-day counters and falsely reports critical pressure (#660/#634).
        # Honor budget_base_dir so isolated/test runs do not read operator spend.
        try:
            from .autonomy import get_budget_snapshot

            snap = get_budget_snapshot(base_dir=self.budget_base_dir) or {}
            try:
                spent_durable = int(snap.get("spent_today") or 0)
            except (TypeError, ValueError):
                spent_durable = 0
            try:
                daily = int(snap.get("daily_limit") or 50000)
            except (TypeError, ValueError):
                daily = 50000
            try:
                per_cycle = int(snap.get("per_cycle_limit") or 8000)
            except (TypeError, ValueError):
                per_cycle = 8000
            if snap.get("remaining_tokens") is not None:
                remaining = int(snap.get("remaining_tokens") or 0)
            elif remaining is None:
                remaining = max(0, daily - spent_durable)
            # Prefer snapshot pressure when present (matches AutonomyEngine rails)
            snap_pressure = str(snap.get("budget_pressure") or "").lower()
            if snap_pressure in ("ok", "elevated", "critical", "exhausted"):
                pressure = snap_pressure
            else:
                rem_i = int(remaining or 0)
                if rem_i <= 0:
                    pressure = "exhausted"
                    would_pause = True
                elif rem_i <= per_cycle:
                    pressure = "critical"
                    would_pause = True
                elif rem_i <= int(daily * 0.25):
                    pressure = "elevated"
            would_pause = bool(snap.get("would_pause") or would_pause)
            try:
                burn = float(snap.get("burn_rate") or 0.0)
            except (TypeError, ValueError):
                burn = (
                    round(min(100.0, (spent_durable / float(daily)) * 100.0), 1)
                    if daily
                    else 0.0
                )
            if burn >= 80 and pressure == "ok":
                pressure = "critical"
            auto["burn_rate"] = burn
        except Exception:
            pass
        # Full cost dashboard only when repo is set (may hit GitHub harvest)
        if self.repo:
            try:
                from .costs import get_cost_dashboard

                dash = get_cost_dashboard(
                    repo=self.repo,
                    autonomy_status={
                        "enabled": bool(auto.get("enabled", False)),
                        "risk_tolerance": str(auto.get("risk_tolerance") or "off"),
                        "budget_remaining_tokens": remaining,
                        "burn_rate": auto.get("burn_rate") or 0.0,
                        "autopilot_score": auto.get("autopilot_score") or 0,
                        "open_human_checkpoints": auto.get("open_human_checkpoints")
                        or [],
                    },
                    budget_base_dir=self.budget_base_dir,
                )
                b = dash.get("budget") or {}
                if b.get("remaining_tokens") is not None:
                    remaining = b.get("remaining_tokens")
                pressure = str(b.get("budget_pressure") or pressure)
                would_pause = bool(b.get("would_pause_next_cycle") or would_pause)
                if b.get("spent_today_durable") is not None:
                    spent_durable = int(b.get("spent_today_durable") or 0)
                if b.get("burn_rate_pct") is not None:
                    auto["burn_rate"] = float(b.get("burn_rate_pct") or 0.0)
            except Exception:
                pass

        return PMStatus(
            enabled=bool(auto.get("enabled", False)),
            risk_tolerance=str(auto.get("risk_tolerance") or "off"),
            budget_remaining_tokens=remaining if remaining is None else int(remaining),
            burn_rate=float(auto.get("burn_rate") or 0.0),
            autopilot_score=int(auto.get("autopilot_score") or 0),
            team_size=len(TEAM),
            open_assignments=by_status["proposed"] + by_status["delegated"],
            open_checkpoints=open_cp_count,
            last_cycle=last_cycle or _now(),
            queue_size=len(self._assignments),
            proposed=by_status["proposed"],
            delegated=by_status["delegated"],
            blocked=by_status["blocked"],
            done=by_status["done"],
            budget_pressure=pressure,
            would_pause_next_cycle=would_pause,
            spent_today_durable=spent_durable,
        )

    def collect_work(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """Gather work candidates from what_next + feed (best-effort)."""
        items: list[dict[str, Any]] = []
        # Avoid importing mcp_server (heavy) and network feed when no repo.
        if not self.repo:
            items.append(
                {
                    "id": "what_next-local",
                    "title": "Inspect plate_health and open Epics",
                    "type": "process",
                    "impact": "medium",
                }
            )
            return items[:limit]
        try:
            from .what_next import get_what_next

            wn = get_what_next(self.repo, "pm")
            impact = (
                "high"
                if wn.get("priority") in ("budget_gate", "open_pr", "ready_issue")
                else "medium"
            )
            row: dict[str, Any] = {
                "id": "what_next",
                "title": wn.get("next_action"),
                "type": "process",
                "prompt_segment": wn.get("prompt_segment"),
                "impact": impact,
                "reason": wn.get("rationale") or "what_next",
                "priority": wn.get("priority"),
                "state_snapshot": wn.get("state_snapshot"),
            }
            if wn.get("issue_number") is not None:
                row["issue_number"] = wn.get("issue_number")
            if wn.get("pr_number") is not None:
                row["pr_number"] = wn.get("pr_number")
            if wn.get("ready_issues"):
                row["ready_issues"] = wn.get("ready_issues")
            items.append(row)
        except Exception:
            items.append(
                {
                    "id": "what_next-fallback",
                    "title": "Inspect plate_health and open Epics",
                    "type": "process",
                    "impact": "medium",
                }
            )
        try:
            from .feed import get_user_feed

            feed = get_user_feed(
                repo=self.repo,
                limit=limit,
                include_process=False,
                include_autonomy=True,
            )
            for it in feed.get("items") or []:
                items.append(it)
        except Exception:
            pass
        return items[:limit]

    def _existing_work_ids(self) -> set[str]:
        active = {"proposed", "delegated", "blocked"}
        return {
            str(a.get("work_id"))
            for a in self._assignments
            if a.get("status") in active and a.get("work_id")
        }

    def run_cycle(
        self,
        *,
        dry_run: bool = True,
        max_assignments: int = 5,
        dispatch_fleet: bool | None = None,
        dispatch_loops: bool | None = None,
        tick_loops: bool = True,
        fetch_loop_gates: bool = False,
    ) -> dict[str, Any]:
        """One PM orchestration cycle; merges new assignments into durable queue.

        When dry_run is False and dispatch_fleet is True (default), delegated
        assignments also open a #644 fleet handoff via handoff_from_pm_assignment.
        When dry_run is False and dispatch_loops is True (default), implement/bugfix
        assignments also start durable #639/#638 feature/bug loops (budget-aware).
        When tick_loops is True (default), syncs existing loop stages onto delegated
        queue rows and completes assignments whose loops reached done.
        """
        ts = _now()
        status = self.get_status()
        do_fleet = self.dispatch_fleet if dispatch_fleet is None else bool(dispatch_fleet)
        do_loops = self.dispatch_loops if dispatch_loops is None else bool(dispatch_loops)
        work = self.collect_work(limit=max(max_assignments * 2, 5))
        # #643: pause items labeled driver:human (human owns; no auto-delegate)
        human_paused: list[dict[str, Any]] = []
        try:
            from .collab import filter_work_for_driver

            split = filter_work_for_driver(work, skip_human_driver=True)
            human_paused = list(split.get("paused_human_driver") or [])
            work = list(split.get("assignable") or work)
        except Exception:
            human_paused = []
        new_assignments: list[dict[str, Any]] = []
        blocked: list[str] = []
        fleet_handoffs: list[dict[str, Any]] = []
        loop_dispatches: list[dict[str, Any]] = []

        if status.open_checkpoints > 0:
            report = {
                "status": "paused",
                "reason": "open human checkpoints",
                "pause_kind": "checkpoints",
                "assignments": [],
                "blocked": ["checkpoints"],
                "pm_status": status.to_dict(),
                "timestamp": ts,
                "dry_run": dry_run,
                "queue_size": len(self._assignments),
                "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'paused', 'ts': ts})}\n{MARKER_END}",
            }
            _ledger_pm(
                "pm_cycle",
                "pause",
                "open human checkpoints",
                risk=status.risk_tolerance,
                metadata={"open_checkpoints": status.open_checkpoints},
            )
            try:
                d = _ensure_pm_dir(self.state_dir)
                (d / LAST_CYCLE_FILE).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
            return report

        # #660/#634 harden: pause PM when durable budget cannot fund a cycle.
        # risk_tolerance=off / enabled=false only disables AutonomyEngine autopilot —
        # surface rails (what_next, costs feed, live loops) still apply (#785/#787).
        if (
            status.budget_pressure in ("critical", "exhausted")
            or status.would_pause_next_cycle
            or (
                status.budget_remaining_tokens is not None
                and int(status.budget_remaining_tokens) <= 0
            )
        ):
            report = {
                "status": "paused",
                "reason": (
                    f"budget_pressure={status.budget_pressure} "
                    f"remaining={status.budget_remaining_tokens} "
                    f"would_pause={status.would_pause_next_cycle} "
                    f"risk={status.risk_tolerance} enabled={status.enabled}"
                ),
                "pause_kind": "budget",
                "assignments": [],
                "blocked": ["budget"],
                "pm_status": status.to_dict(),
                "timestamp": ts,
                "dry_run": dry_run,
                "queue_size": len(self._assignments),
                "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'paused', 'kind': 'budget', 'ts': ts})}\n{MARKER_END}",
            }
            _ledger_pm(
                "pm_cycle",
                "pause",
                report["reason"],
                risk=status.risk_tolerance,
                metadata={
                    "budget_pressure": status.budget_pressure,
                    "remaining": status.budget_remaining_tokens,
                },
            )
            try:
                d = _ensure_pm_dir(self.state_dir)
                (d / LAST_CYCLE_FILE).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass
            return report

        budget = status.budget_remaining_tokens
        # #885: after open-checkpoint + budget gates clear, promote proposed
        # high-impact assignments whose #648 checkpoints are approved.
        promotions = self.promote_checkpoint_ready_assignments(
            dry_run=dry_run,
            dispatch_fleet=do_fleet,
            dispatch_loops=do_loops,
            budget_remaining=budget,
        )
        seen = self._existing_work_ids()
        for item in work:
            if len(new_assignments) >= max_assignments:
                break
            wid = str(item.get("id") or item.get("number") or item.get("title") or "")
            if wid and wid in seen:
                continue
            asg = assign_work(
                item,
                risk_tolerance=status.risk_tolerance,
                budget_remaining=budget,
                open_checkpoint=not dry_run,
                checkpoint_base_dir=self.checkpoint_base_dir,
            )
            if asg["status"] == "blocked":
                blocked.append(asg["assignment_id"])
            else:
                if budget is not None:
                    budget = max(0, int(budget) - int(asg["estimated_tokens"]))
                if not dry_run:
                    if asg.get("requires_checkpoint") and asg.get("checkpoint_id"):
                        # leave proposed until checkpoint approved
                        asg["status"] = "proposed"
                    else:
                        asg["status"] = "delegated"
                        try:
                            from .baseline_catalog import delegate_to_agent

                            delegate_to_agent(
                                agent_id="plate",
                                prompt_segment=asg["packet"].get("prompt_segment", ""),
                                context={
                                    "pm_assignment": asg["assignment_id"],
                                    "persona": asg["agent_id"],
                                    "work_type": asg["work_type"],
                                },
                            )
                        except Exception:
                            pass
                        # #660/#644: open durable fleet handoff for multi-agent execution
                        if do_fleet:
                            try:
                                from .fleet import handoff_from_pm_assignment

                                ho = handoff_from_pm_assignment(
                                    asg,
                                    budget_remaining=budget,
                                    open_checkpoint=bool(asg.get("requires_checkpoint")),
                                    base_dir=self.fleet_base_dir,
                                    record_ledger=True,
                                )
                                if ho.get("ok"):
                                    hid = (ho.get("handoff") or {}).get("handoff_id")
                                    asg["fleet_handoff_id"] = hid
                                    asg.setdefault("packet", {})["fleet_handoff_id"] = hid
                                    if ho.get("checkpoint_id"):
                                        asg.setdefault("packet", {})[
                                            "fleet_checkpoint_id"
                                        ] = ho["checkpoint_id"]
                                    fleet_handoffs.append(
                                        {
                                            "assignment_id": asg.get("assignment_id"),
                                            "handoff_id": hid,
                                            "to_agent": (ho.get("handoff") or {}).get(
                                                "to_agent"
                                            ),
                                            "status": (ho.get("handoff") or {}).get(
                                                "status"
                                            ),
                                            "checkpoint_id": ho.get("checkpoint_id"),
                                        }
                                    )
                                elif ho.get("blocked"):
                                    asg["status"] = "blocked"
                                    asg.setdefault("packet", {})["fleet_block"] = ho.get(
                                        "error"
                                    )
                                    blocked.append(asg["assignment_id"])
                            except Exception as exc:
                                asg.setdefault("packet", {})["fleet_error"] = str(exc)
                        # #660/#638/#639: open durable feature/bug loop for implement/bugfix
                        if do_loops and asg.get("status") == "delegated":
                            try:
                                asg["risk_tolerance"] = status.risk_tolerance
                                loop_out = dispatch_loop_from_assignment(
                                    asg,
                                    budget_remaining=budget,
                                    feature_loop_base_dir=self.feature_loop_base_dir,
                                    bug_loop_base_dir=self.bug_loop_base_dir,
                                    artifact_base_dir=self.artifact_base_dir,
                                    budget_base_dir=self.budget_base_dir,
                                    record_ledger=True,
                                )
                                if loop_out.get("skipped"):
                                    asg.setdefault("packet", {})["loop_skip"] = loop_out.get(
                                        "reason"
                                    )
                                elif loop_out.get("ok") or loop_out.get("run_id"):
                                    asg["loop_run_id"] = loop_out.get("run_id")
                                    asg["loop_kind"] = loop_out.get("loop_kind")
                                    asg.setdefault("packet", {})["loop_run_id"] = loop_out.get(
                                        "run_id"
                                    )
                                    asg.setdefault("packet", {})["loop_kind"] = loop_out.get(
                                        "loop_kind"
                                    )
                                    asg.setdefault("packet", {})["loop_stage"] = loop_out.get(
                                        "stage"
                                    )
                                    if loop_out.get("loop_kind") == "artifact":
                                        asg.setdefault("packet", {})[
                                            "artifact_proposal_id"
                                        ] = loop_out.get("run_id")
                                        if loop_out.get("ask_user_question"):
                                            asg.setdefault("packet", {})[
                                                "artifact_ask_user_question"
                                            ] = loop_out["ask_user_question"]
                                    if loop_out.get("blocked"):
                                        asg["status"] = "blocked"
                                        asg.setdefault("packet", {})["loop_block"] = loop_out.get(
                                            "error"
                                        )
                                        blocked.append(asg["assignment_id"])
                                    loop_dispatches.append(
                                        {
                                            "assignment_id": asg.get("assignment_id"),
                                            "loop_kind": loop_out.get("loop_kind"),
                                            "run_id": loop_out.get("run_id"),
                                            "stage": loop_out.get("stage"),
                                            "blocked": bool(loop_out.get("blocked")),
                                        }
                                    )
                                elif loop_out.get("blocked"):
                                    asg["status"] = "blocked"
                                    asg.setdefault("packet", {})["loop_block"] = loop_out.get(
                                        "error"
                                    )
                                    blocked.append(asg["assignment_id"])
                            except Exception as exc:
                                asg.setdefault("packet", {})["loop_error"] = str(exc)
            asg["ask_user_question"] = build_assignment_tui(asg)
            new_assignments.append(asg)
            seen.add(str(asg.get("work_id") or ""))

        # merge into durable queue (replace same assignment_id if re-run)
        by_id = {a.get("assignment_id"): a for a in self._assignments}
        for a in new_assignments:
            by_id[a.get("assignment_id")] = a
        self._assignments = list(by_id.values())
        try:
            self._save_queue()
        except Exception:
            pass

        # #660 deepen: tick existing delegated loops (stage sync + complete-on-done)
        loop_ticks: list[dict[str, Any]] = []
        if tick_loops:
            try:
                loop_ticks = self.tick_delegated_loops(
                    dry_run=dry_run,
                    fetch_gates=bool(fetch_loop_gates and not dry_run),
                    limit=max(max_assignments * 2, 10),
                    complete_when_done=True,
                )
            except Exception as exc:
                loop_ticks = [{"ok": False, "error": str(exc)}]

        try:
            d = _ensure_pm_dir(self.state_dir)
            (d / LAST_CYCLE_FILE).write_text(
                json.dumps(
                    {
                        "timestamp": ts,
                        "assignments": new_assignments,
                        "blocked": blocked,
                        "fleet_handoffs": fleet_handoffs,
                        "loop_dispatches": loop_dispatches,
                        "loop_ticks": loop_ticks,
                        "pm_status": status.to_dict(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

        report = {
            "status": "completed",
            "assignments": new_assignments,
            "blocked": blocked,
            "fleet_handoffs": fleet_handoffs,
            "loop_dispatches": loop_dispatches,
            "loop_ticks": loop_ticks,
            "promotions": promotions,
            "human_paused": [
                {
                    "id": x.get("id") or x.get("number"),
                    "title": x.get("title"),
                    "driver": "human",
                }
                for x in human_paused
            ],
            "pm_status": self.get_status().to_dict(),
            "work_considered": len(work) + len(human_paused),
            "timestamp": ts,
            "dry_run": dry_run,
            "dispatch_fleet": do_fleet and not dry_run,
            "dispatch_loops": do_loops and not dry_run,
            "tick_loops": bool(tick_loops),
            "queue_size": len(self._assignments),
            "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'completed', 'n': len(new_assignments), 'fleet': len(fleet_handoffs), 'loops': len(loop_dispatches), 'ticks': len(loop_ticks), 'promotions': len(promotions), 'ts': ts})}\n{MARKER_END}",
        }
        _ledger_pm(
            "pm_cycle",
            "proceed" if not dry_run else "shadow",
            f"cycle completed n={len(new_assignments)} blocked={len(blocked)} fleet={len(fleet_handoffs)} loops={len(loop_dispatches)} ticks={len(loop_ticks)} promotions={len(promotions)}",
            cost=sum(int(a.get("estimated_tokens") or 0) for a in new_assignments),
            risk=status.risk_tolerance,
            metadata={
                "dry_run": dry_run,
                "n": len(new_assignments),
                "n_fleet": len(fleet_handoffs),
                "n_loop_ticks": len(loop_ticks),
                "n_promotions": len(promotions),
            },
        )
        return report

    def run_loop(
        self,
        *,
        max_cycles: int = 3,
        dry_run: bool = True,
        max_assignments: int = 5,
        stop_on_pause: bool = True,
        dispatch_fleet: bool | None = None,
        dispatch_loops: bool | None = None,
    ) -> dict[str, Any]:
        """Multi-cycle orchestrator loop with budget/checkpoint stop conditions."""
        cycles: list[dict[str, Any]] = []
        stopped_reason = "max_cycles"
        for i in range(max(1, max_cycles)):
            rep = self.run_cycle(
                dry_run=dry_run,
                max_assignments=max_assignments,
                dispatch_fleet=dispatch_fleet,
                dispatch_loops=dispatch_loops,
            )
            cycles.append(
                {
                    "cycle": i + 1,
                    "status": rep.get("status"),
                    "n_assignments": len(rep.get("assignments") or []),
                    "blocked": len(rep.get("blocked") or []),
                    "n_fleet": len(rep.get("fleet_handoffs") or []),
                    "n_loops": len(rep.get("loop_dispatches") or []),
                    "queue_size": rep.get("queue_size"),
                }
            )
            if rep.get("status") == "paused" and stop_on_pause:
                kind = str(rep.get("pause_kind") or "checkpoints")
                stopped_reason = (
                    "paused_budget" if kind == "budget" else "paused_checkpoints"
                )
                break
            st = rep.get("pm_status") or {}
            rem = st.get("budget_remaining_tokens")
            if rem is not None and int(rem) <= 0:
                stopped_reason = "budget_exhausted"
                break
            if str(st.get("budget_pressure") or "") in ("critical", "exhausted"):
                stopped_reason = "budget_pressure"
                break
            # no new work
            if not (rep.get("assignments") or []) and not (rep.get("blocked") or []):
                if i > 0:
                    stopped_reason = "idle"
                    break
        out = {
            "status": "completed",
            "cycles": cycles,
            "n_cycles": len(cycles),
            "stopped_reason": stopped_reason,
            "pm_status": self.get_status().to_dict(),
            "queue": self.list_queue(status="all", limit=20),
            "dry_run": dry_run,
            "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'loop', 'n': len(cycles), 'stop': stopped_reason})}\n{MARKER_END}",
        }
        _ledger_pm(
            "pm_loop",
            "proceed" if not dry_run else "shadow",
            f"loop stopped={stopped_reason} cycles={len(cycles)}",
            risk=str((out["pm_status"] or {}).get("risk_tolerance") or ""),
            metadata={"stopped_reason": stopped_reason, "n_cycles": len(cycles)},
        )
        return out


def get_pm_status(repo: str | None = None, state_dir: Path | None = None) -> dict[str, Any]:
    return ProjectManager(repo=repo, state_dir=state_dir).get_status().to_dict()


def run_pm_cycle(
    repo: str | None = None,
    dry_run: bool = True,
    max_assignments: int = 5,
    state_dir: Path | None = None,
    dispatch_fleet: bool = True,
    dispatch_loops: bool = True,
    tick_loops: bool = True,
    fetch_loop_gates: bool = False,
    fleet_base_dir: Path | None = None,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
) -> dict[str, Any]:
    return ProjectManager(
        repo=repo,
        state_dir=state_dir,
        fleet_base_dir=fleet_base_dir,
        feature_loop_base_dir=feature_loop_base_dir,
        bug_loop_base_dir=bug_loop_base_dir,
        dispatch_fleet=dispatch_fleet,
        dispatch_loops=dispatch_loops,
    ).run_cycle(
        dry_run=dry_run,
        max_assignments=max_assignments,
        dispatch_fleet=dispatch_fleet,
        dispatch_loops=dispatch_loops,
        tick_loops=tick_loops,
        fetch_loop_gates=fetch_loop_gates,
    )


def tick_pm_loops(
    repo: str | None = None,
    *,
    dry_run: bool = True,
    fetch_gates: bool = False,
    limit: int = 20,
    complete_when_done: bool = True,
    state_dir: Path | None = None,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
) -> dict[str, Any]:
    """Dedicated surface: tick delegated #638/#639 loops without a full PM assign cycle.

    Useful for host loops that only need stage sync / estimate_cost advance / babysit
    gates / complete-on-done after work was already delegated.
    """
    pm = ProjectManager(
        repo=repo,
        state_dir=state_dir,
        feature_loop_base_dir=feature_loop_base_dir,
        bug_loop_base_dir=bug_loop_base_dir,
        dispatch_fleet=False,
        dispatch_loops=False,
    )
    ticks = pm.tick_delegated_loops(
        dry_run=dry_run,
        fetch_gates=fetch_gates,
        limit=limit,
        complete_when_done=complete_when_done,
    )
    completed = sum(1 for t in ticks if t.get("completed_assignment"))
    advanced = sum(1 for t in ticks if t.get("advanced"))
    return {
        "ok": True,
        "dry_run": dry_run,
        "loop_ticks": ticks,
        "n_ticks": len(ticks),
        "n_advanced": advanced,
        "n_completed": completed,
        "queue_size": len(pm._assignments),
        "pm_status": pm.get_status().to_dict(),
        "marker": (
            f"{MARKER_BEGIN}\n"
            f'{json.dumps({"status": "tick_loops", "n": len(ticks), "advanced": advanced, "completed": completed})}\n'
            f"{MARKER_END}"
        ),
    }


def run_pm_loop(
    repo: str | None = None,
    dry_run: bool = True,
    max_cycles: int = 3,
    max_assignments: int = 5,
    state_dir: Path | None = None,
    dispatch_fleet: bool = True,
    dispatch_loops: bool = True,
    fleet_base_dir: Path | None = None,
    feature_loop_base_dir: Path | None = None,
    bug_loop_base_dir: Path | None = None,
) -> dict[str, Any]:
    return ProjectManager(
        repo=repo,
        state_dir=state_dir,
        fleet_base_dir=fleet_base_dir,
        feature_loop_base_dir=feature_loop_base_dir,
        bug_loop_base_dir=bug_loop_base_dir,
        dispatch_fleet=dispatch_fleet,
        dispatch_loops=dispatch_loops,
    ).run_loop(
        max_cycles=max_cycles,
        dry_run=dry_run,
        max_assignments=max_assignments,
        dispatch_fleet=dispatch_fleet,
    )


def list_pm_queue(
    repo: str | None = None,
    status: str | None = None,
    limit: int = 50,
    state_dir: Path | None = None,
) -> list[dict[str, Any]]:
    return ProjectManager(repo=repo, state_dir=state_dir).list_queue(status=status, limit=limit)


def complete_pm_assignment(
    assignment_id: str,
    *,
    status: str = "done",
    note: str = "",
    state_dir: Path | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    return ProjectManager(repo=repo, state_dir=state_dir).complete_assignment(
        assignment_id, status=status, note=note
    )


def pm_feed_items(
    *,
    state_dir: Path | None = None,
    repo: str | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Feed rows for open PM assignments + pause gates (#660)."""
    pm = ProjectManager(repo=repo, state_dir=state_dir)
    items: list[dict[str, Any]] = []
    st = pm.get_status()
    if st.open_checkpoints > 0:
        items.append(
            {
                "id": "pm-pause-checkpoints",
                "item_type": "pm_gate",
                "title": f"PM paused: {st.open_checkpoints} open checkpoint(s)",
                "rank": 8,
                "impact": "high",
                "status": "paused",
                "reason": "Open human checkpoints block PM assign/delegate",
                "prompt_segment": (
                    "Resolve open checkpoints (plate_checkpoint_decide) before "
                    "plate_pm_run_cycle --apply."
                ),
                "ask_user_question": {
                    "question": "PM is paused on open checkpoints — next step?",
                    "options": [
                        {
                            "id": "list_checkpoints",
                            "label": "List open checkpoints",
                            "description": "gh plate checkpoint --list / plate_checkpoint_list",
                        },
                        {
                            "id": "status",
                            "label": "PM status",
                            "description": "gh plate pm --status",
                        },
                    ],
                },
                "source": "pm",
            }
        )
    if st.enabled and st.risk_tolerance not in ("off", "") and (
        st.budget_pressure in ("critical", "exhausted") or st.would_pause_next_cycle
    ):
        items.append(
            {
                "id": "pm-pause-budget",
                "item_type": "pm_gate",
                "title": (
                    f"PM budget gate: pressure={st.budget_pressure} "
                    f"remaining={st.budget_remaining_tokens}"
                ),
                "rank": 7,
                "impact": "critical" if st.budget_pressure == "exhausted" else "high",
                "status": "paused",
                "reason": "Budget rails block unsupervised PM cycles (#634/#660)",
                "prompt_segment": (
                    "Raise .plate token_budget / cost_ceiling or wait for UTC day reset; "
                    "gh plate costs --dashboard."
                ),
                "ask_user_question": {
                    "question": "PM budget pressure high — next step?",
                    "options": [
                        {
                            "id": "dashboard",
                            "label": "Open cost dashboard",
                            "description": "gh plate costs --dashboard",
                        },
                        {
                            "id": "raise_budget",
                            "label": "Raise token_budget in .plate",
                            "description": "Human edits autonomy.token_budget",
                        },
                        {
                            "id": "pause",
                            "label": "Keep autonomy off / pause",
                            "description": "No unsupervised PM cycles",
                        },
                    ],
                },
                "source": "pm",
            }
        )
    for st_name in ("blocked", "proposed", "delegated"):
        for row in pm.list_queue(status=st_name, limit=limit):
            aid = str(row.get("assignment_id") or "")
            items.append(
                {
                    "id": aid,
                    "item_type": "pm_assignment",
                    "title": row.get("work_title") or aid,
                    "rank": 9 if st_name == "blocked" else 17,
                    "impact": "high" if st_name == "blocked" else "medium",
                    "status": st_name,
                    "agent_id": row.get("agent_id"),
                    "work_type": row.get("work_type"),
                    "reason": row.get("rationale") or f"PM assignment {st_name}",
                    "prompt_segment": (
                        f"PM [{st_name}] {row.get('work_title')}: "
                        f"persona={row.get('agent_id')}; "
                        f"plate_pm_complete {aid} when done."
                    ),
                    "ask_user_question": row.get("ask_user_question")
                    or build_assignment_tui(row),
                    "source": "pm_queue",
                    "assignment_id": aid,
                }
            )
    items.sort(key=lambda x: (int(x.get("rank") or 99), str(x.get("title") or "")))
    return items[: max(1, limit)]
