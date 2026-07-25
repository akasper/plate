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
    out["ask_user_question"] = build_assignment_tui(out)
    return out


def _count_open_checkpoints(checkpoint_base_dir: Path | None = None) -> int:
    """Count pending #648 checkpoints (local durable) plus best-effort."""
    try:
        from .checkpoint import list_checkpoints

        rows = list_checkpoints(status="pending", base_dir=checkpoint_base_dir, limit=100)
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
    ):
        self.repo = repo
        self.state_dir = state_dir
        self.checkpoint_base_dir = checkpoint_base_dir
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

        return PMStatus(
            enabled=bool(auto.get("enabled", False)),
            risk_tolerance=str(auto.get("risk_tolerance") or "off"),
            budget_remaining_tokens=auto.get("budget_remaining_tokens"),
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
            from .mcp_server import _what_next

            wn = _what_next(self.repo, "pm")
            items.append(
                {
                    "id": "what_next",
                    "title": wn.get("next_action"),
                    "type": "process",
                    "prompt_segment": wn.get("prompt_segment"),
                    "impact": "medium",
                    "reason": wn.get("rationale") or "what_next",
                }
            )
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

    def run_cycle(self, *, dry_run: bool = True, max_assignments: int = 5) -> dict[str, Any]:
        """One PM orchestration cycle; merges new assignments into durable queue."""
        ts = _now()
        status = self.get_status()
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

        if status.open_checkpoints > 0:
            report = {
                "status": "paused",
                "reason": "open human checkpoints",
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

        budget = status.budget_remaining_tokens
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

        try:
            d = _ensure_pm_dir(self.state_dir)
            (d / LAST_CYCLE_FILE).write_text(
                json.dumps(
                    {
                        "timestamp": ts,
                        "assignments": new_assignments,
                        "blocked": blocked,
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
            "queue_size": len(self._assignments),
            "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'completed', 'n': len(new_assignments), 'ts': ts})}\n{MARKER_END}",
        }
        _ledger_pm(
            "pm_cycle",
            "proceed" if not dry_run else "shadow",
            f"cycle completed n={len(new_assignments)} blocked={len(blocked)}",
            cost=sum(int(a.get("estimated_tokens") or 0) for a in new_assignments),
            risk=status.risk_tolerance,
            metadata={"dry_run": dry_run, "n": len(new_assignments)},
        )
        return report

    def run_loop(
        self,
        *,
        max_cycles: int = 3,
        dry_run: bool = True,
        max_assignments: int = 5,
        stop_on_pause: bool = True,
    ) -> dict[str, Any]:
        """Multi-cycle orchestrator loop with budget/checkpoint stop conditions."""
        cycles: list[dict[str, Any]] = []
        stopped_reason = "max_cycles"
        for i in range(max(1, max_cycles)):
            rep = self.run_cycle(dry_run=dry_run, max_assignments=max_assignments)
            cycles.append(
                {
                    "cycle": i + 1,
                    "status": rep.get("status"),
                    "n_assignments": len(rep.get("assignments") or []),
                    "blocked": len(rep.get("blocked") or []),
                    "queue_size": rep.get("queue_size"),
                }
            )
            if rep.get("status") == "paused" and stop_on_pause:
                stopped_reason = "paused_checkpoints"
                break
            st = rep.get("pm_status") or {}
            rem = st.get("budget_remaining_tokens")
            if rem is not None and int(rem) <= 0:
                stopped_reason = "budget_exhausted"
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
) -> dict[str, Any]:
    return ProjectManager(repo=repo, state_dir=state_dir).run_cycle(
        dry_run=dry_run, max_assignments=max_assignments
    )


def run_pm_loop(
    repo: str | None = None,
    dry_run: bool = True,
    max_cycles: int = 3,
    max_assignments: int = 5,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    return ProjectManager(repo=repo, state_dir=state_dir).run_loop(
        max_cycles=max_cycles,
        dry_run=dry_run,
        max_assignments=max_assignments,
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
