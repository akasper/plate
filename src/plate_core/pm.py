"""Project Manager / Orchestrator core (#660).

Long-running coordination loop: poll what_next + feed signals, assign work to
specialized personas within budget, surface checkpoints, and emit quiet cycle
reports. GitHub remains source of truth; this module holds ephemeral runtime
queue state and durable markers under .agentic/pm/.

v1 slice (not full multi-agent runtime):
- Team catalog of developer/designer/research/release personas
- Budget-aware assignment heuristic from item type + risk
- One orchestration cycle: introspect → rank work → assign (or checkpoint) → report
- MCP/CLI surfaces for status, team list, run_cycle, assign
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PM_DIR = Path(".agentic/pm")
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
    status: str = "proposed"  # proposed | delegated | blocked | done
    packet: dict[str, Any] = field(default_factory=dict)

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


def assign_work(
    item: dict[str, Any],
    *,
    risk_tolerance: str = "medium",
    budget_remaining: int | None = None,
) -> dict[str, Any]:
    """Create a budget-aware assignment packet for one work item."""
    work_type = classify_work_type(item)
    est = estimate_assignment_tokens(work_type)
    impact = str(item.get("impact") or "medium").lower()
    requires_cp = work_type in ("release", "checkpoint") or impact in ("high", "critical")
    agent = pick_agent(work_type, risk_tolerance)

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
        status="blocked" if blocked else ("blocked" if requires_cp and risk_tolerance == "low" else "proposed"),
        packet={
            "agent_id": agent["id"],
            "persona": agent,
            "task_summary": str(item.get("title") or item.get("next_action") or ""),
            "prompt_segment": item.get("prompt_segment")
            or f"Execute {work_type} for: {item.get('title')}. Follow TDD, quiet ops, Closes in PR body.",
            "impact": impact,
            "source_item": {k: item[k] for k in item if k in ("id", "number", "url", "item_type", "type", "reason")},
        },
    )
    if requires_cp and not blocked:
        assignment.status = "proposed"
        assignment.rationale += "; high-impact: surface checkpoint before execute"
    return assignment.to_dict()


class ProjectManager:
    """Budget-aware orchestrator cycle runner."""

    def __init__(self, repo: str | None = None, state_dir: Path | None = None):
        self.repo = repo
        self.state_dir = state_dir
        self._assignments: list[dict[str, Any]] = []

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
        open_cps = list(auto.get("open_human_checkpoints") or [])
        return PMStatus(
            enabled=bool(auto.get("enabled", False)),
            risk_tolerance=str(auto.get("risk_tolerance") or "off"),
            budget_remaining_tokens=auto.get("budget_remaining_tokens"),
            burn_rate=float(auto.get("burn_rate") or 0.0),
            autopilot_score=int(auto.get("autopilot_score") or 0),
            team_size=len(TEAM),
            open_assignments=len([a for a in self._assignments if a.get("status") == "proposed"]),
            open_checkpoints=len(open_cps),
            last_cycle=_now(),
            queue_size=len(self._assignments),
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

    def run_cycle(self, *, dry_run: bool = True, max_assignments: int = 5) -> dict[str, Any]:
        """One PM orchestration cycle."""
        ts = _now()
        status = self.get_status()
        work = self.collect_work(limit=max(max_assignments * 2, 5))
        assignments: list[dict[str, Any]] = []
        blocked: list[str] = []

        if status.open_checkpoints > 0:
            return {
                "status": "paused",
                "reason": "open human checkpoints",
                "assignments": [],
                "blocked": ["checkpoints"],
                "pm_status": status.to_dict(),
                "timestamp": ts,
                "dry_run": dry_run,
                "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'paused', 'ts': ts})}\n{MARKER_END}",
            }

        budget = status.budget_remaining_tokens
        for item in work:
            if len(assignments) >= max_assignments:
                break
            asg = assign_work(
                item,
                risk_tolerance=status.risk_tolerance,
                budget_remaining=budget,
            )
            if asg["status"] == "blocked":
                blocked.append(asg["assignment_id"])
            else:
                if budget is not None:
                    budget = max(0, int(budget) - int(asg["estimated_tokens"]))
                if not dry_run:
                    asg["status"] = "delegated"
                    # best-effort narrow packet via baseline catalog
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
            assignments.append(asg)

        self._assignments = assignments
        # persist last cycle
        try:
            d = _ensure_pm_dir(self.state_dir)
            (d / "last_cycle.json").write_text(
                json.dumps(
                    {
                        "timestamp": ts,
                        "assignments": assignments,
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
            "assignments": assignments,
            "blocked": blocked,
            "pm_status": status.to_dict(),
            "work_considered": len(work),
            "timestamp": ts,
            "dry_run": dry_run,
            "marker": f"{MARKER_BEGIN}\n{json.dumps({'status': 'completed', 'n': len(assignments), 'ts': ts})}\n{MARKER_END}",
        }
        return report


def get_pm_status(repo: str | None = None) -> dict[str, Any]:
    return ProjectManager(repo=repo).get_status().to_dict()


def run_pm_cycle(
    repo: str | None = None,
    dry_run: bool = True,
    max_assignments: int = 5,
) -> dict[str, Any]:
    return ProjectManager(repo=repo).run_cycle(dry_run=dry_run, max_assignments=max_assignments)
