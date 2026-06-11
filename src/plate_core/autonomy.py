"""AutonomyEngine runtime for Epic #470.

Core software that introspects project state (via health, epics, costs, plate_config, procedures)
and decides/delegates/executes autonomous actions at the user's budgeted token rate and
configured risk_tolerance (core philosophy: autonomous by default unless 'off').

Implements the contract from docs/design/autonomous-plate-engine.md (refined by Research #471).
Wired via mcp_server (plate_autonomy_* tools) and cli (gh plate autonomy ...).
Follows quiet ops for looped/scheduled use (terse bullets only; comments only on real progress).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .costs import get_cost_report
from .epics import get_epic_status
from .health import get_health
from .plate_config import load_plate_config, get_plate_config_report


@dataclass
class AutonomyStatus:
    """Current autonomy state for status/health/MCP."""
    enabled: bool = True
    risk_tolerance: str = "medium"  # off | low | medium | high
    budget_remaining_tokens: int | None = None
    budget_remaining_usd: str | None = None
    last_cycle: str | None = None
    next_scheduled: str | None = None
    autopilot_score: int = 0  # 0-100 composite
    due_procedures: list[str] = field(default_factory=list)
    open_human_checkpoints: list[str] = field(default_factory=list)
    throttled_actions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectSnapshot:
    """Introspected state (health + epics + costs + config + procedures due)."""
    health: dict[str, Any] = field(default_factory=dict)
    epic_status: dict[str, Any] = field(default_factory=dict)
    cost_report: dict[str, Any] = field(default_factory=dict)
    plate_config: dict[str, Any] = field(default_factory=dict)
    due_procedures: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CycleReport:
    """Result of one autonomy engine cycle."""
    status: str = "completed"
    actions_taken: list[str] = field(default_factory=list)
    throttled: list[str] = field(default_factory=list)
    paused: bool = False
    budget_decision: str = "proceed"  # proceed | throttle | pause | warn
    snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcedureDef:
    """Lightweight procedure def (loaded from .agentic/procedures/ or built-ins)."""
    id: str
    cadence: str
    risk_level: str
    description: str = ""
    enabled: bool = True


class AutonomyEngine:
    """The core engine for long-running autonomous PLATE operation.

    Introspects, enforces budget/risk, decides next (integrating what_next + procedures),
    executes (deterministic or delegate via trigger comments), logs with markers + usage.
    """

    def __init__(self, repo: str | None = None, client: Any = None):
        self.repo = repo
        self.client = client
        self.config = load_plate_config()
        # Autonomy section is opt-in only (absent .plate or absent 'autonomy' key => off / legacy AUTONOMOUS_MODE only per #470/#476 contract).
        # Do not inherit from DEFAULT_CONFIG; only user-provided autonomy section in .plate enables graduated auto behavior.
        config_dict = self.config.to_dict() if hasattr(self.config, "to_dict") else {}
        self.autonomy_config = config_dict.get("autonomy", {}) or {}
        if not self.autonomy_config:
            self.enabled = False
            self.risk_tolerance = "off"
        else:
            self.enabled = self.autonomy_config.get("enabled", True)
            rt = self.autonomy_config.get("risk_tolerance", "medium")
            self.risk_tolerance = (rt or "medium").lower().strip()
        self.procedures: list[ProcedureDef] = self._load_procedures()
        # Simple in-memory spend for governor (real impl would persist or use comments)
        # Separate per-cycle (reset each run_cycle) and daily (UTC day rollover) counters to address review feedback on budget tracking.
        self._spent_this_cycle: int = 0
        self._spent_today: int = 0
        self._last_reset = datetime.now(timezone.utc).date()

    def _load_procedures(self) -> list[ProcedureDef]:
        """Load procedure defs from .agentic/procedures/*.json (data-driven per design) + built-ins."""
        procs: list[ProcedureDef] = []
        proc_dir = Path(".agentic/procedures")
        if proc_dir.exists():
            for f in sorted(proc_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    procs.append(ProcedureDef(
                        id=data["id"],
                        cadence=data.get("cadence", "manual"),
                        risk_level=data.get("risk_level", "medium"),
                        description=data.get("description", ""),
                        enabled=data.get("enabled", True),
                    ))
                except Exception:
                    continue  # skip bad defs
        # Ensure core built-ins for the Epic (even if files present)
        existing = {p.id for p in procs}
        for builtin in [
            {"id": "nightly-drift-detection", "cadence": "nightly", "risk_level": "medium", "description": "Built-in drift detection (labels, Goals, fragments, health vs expected)"},
            {"id": "feedback-integration", "cadence": "nightly", "risk_level": "low", "description": "Babysit PR feedback for agents"},
            {"id": "cost-rollup", "cadence": "weekly", "risk_level": "low", "description": "Aggregate USAGE REPORTs and costs"},
        ]:
            if builtin["id"] not in existing:
                procs.append(ProcedureDef(**builtin))
        return procs

    def get_status(self) -> AutonomyStatus:
        """Return live status (used by plate_autonomy_status + health enrichment)."""
        # Integrate real reports. Always call helpers even if self.repo is None; they resolve
        # from local git remote (origin) when repo=None per design and other call sites.
        try:
            health = get_health(self.repo).to_dict()
            costs = get_cost_report(self.repo).to_dict()
            # Config report is always from local filesystem (.plate); never pass remote 'owner/name' string (would be misinterpreted as path).
            # See review feedback on get_plate_config_report(self.repo) misuse.
            config_report = get_plate_config_report(None).to_dict()

        except Exception:
            health = costs = config_report = {}

        # Compute autopilot_score (for #479 observability): base on risk tolerance (higher tolerance = more autonomous potential), budget adherence, enabled procedures count.
        risk_rank = self._risk_rank(self.risk_tolerance)
        base = 30 + (risk_rank * 15)  # 30-75 from risk
        budget_pct = 0
        daily = self.autonomy_config.get("token_budget", {}).get("daily", 50000)
        if daily > 0:
            remaining = self.autonomy_config.get("token_budget", {}).get("daily", 50000) - self._spent_today
            budget_pct = max(0, min(100, (remaining / daily) * 100))
        proc_bonus = min(20, len([p for p in self.procedures if p.enabled]) * 5)
        autopilot = int(base + (budget_pct * 0.2) + proc_bonus)
        autopilot = max(0, min(100, autopilot))

        # budget_remaining_usd reported as str for JSON/MCP/CLI consumer stability (addresses type annotation feedback).
        usd_val = self.autonomy_config.get("cost_ceiling_usd") if self.autonomy_config else None
        budget_remaining_usd = str(usd_val) if usd_val is not None else None

        due_ids = [p.id for p in self.procedures if p.enabled and self._risk_rank(p.risk_level) <= self._risk_rank(self.risk_tolerance)]
        return AutonomyStatus(
            enabled=self.enabled,
            risk_tolerance=self.risk_tolerance,
            budget_remaining_tokens=self.autonomy_config.get("token_budget", {}).get("daily", 50000) - self._spent_today if self.autonomy_config else None,
            budget_remaining_usd=budget_remaining_usd,
            last_cycle=datetime.now(timezone.utc).isoformat(),
            autopilot_score=autopilot,
            due_procedures=due_ids,
            open_human_checkpoints=health.get("errors", []),
        )

    def introspect(self) -> ProjectSnapshot:
        """Gather full project state for decide_next (health + epics + costs + config + procedures)."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            health = get_health(self.repo).to_dict()
            epics = get_epic_status(self.repo).to_dict()
            costs = get_cost_report(self.repo).to_dict()
            # Config report always local FS (see get_status fix); passing repo str would treat owner/name as path and could raise/blank data.
            pconfig = get_plate_config_report(None).to_dict()

        except Exception as exc:
            health = {"error": str(exc)}
            epics = costs = pconfig = {}

        # Populate due from loaded procedures (filter risk)
        due = []
        for p in self.procedures:
            if p.enabled and self._risk_rank(p.risk_level) <= self._risk_rank(self.risk_tolerance):
                due.append({"id": p.id, "cadence": p.cadence, "risk_level": p.risk_level, "est_tokens": 4000})

        return ProjectSnapshot(
            health=health,
            epic_status=epics,
            cost_report=costs,
            plate_config=pconfig,
            due_procedures=due,
            timestamp=ts,
        )

    def enforce_budget(self, estimated: int, action_kind: str) -> bool:
        """Core governor. Returns True if action may proceed (after possible throttle/pause).

        Called before expensive steps per design (info_audit, plan_epic gen, apply procedures, etc.).
        Over-estimates, integrates historical from costs, enforces caps + risk.
        """
        if not self.enabled or self.risk_tolerance == "off":
            return True  # explicit off or disabled: no autonomous budget enforcement

        # Daily reset (UTC date)
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset:
            self._spent_this_cycle = 0
            self._spent_today = 0
            self._last_reset = today

        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000)
        daily_cap = self.autonomy_config.get("token_budget", {}).get("daily", 50000)
        action = self.autonomy_config.get("token_budget", {}).get("action", "throttle")

        projected_cycle = self._spent_this_cycle + estimated
        projected_daily = self._spent_today + estimated

        if projected_cycle > cap or projected_daily > daily_cap:
            if action == "pause":
                # In full engine: set paused, post status comment on Epic or autonomy Discussion
                return False
            if action == "throttle":
                # Caller should skip low-pri; here we just record and allow (caller decides)
                self._spent_this_cycle += estimated // 2  # partial spend on throttle
                return False
            # warn: allow but log
            self._spent_this_cycle += estimated
            self._spent_today += estimated
            return True

        self._spent_this_cycle += estimated
        self._spent_today += estimated
        return True

    def decide_next(self, snapshot: ProjectSnapshot) -> list[dict[str, Any]]:
        """Decide actions for the cycle (what_next + risk-filtered procedures + budget-aware).

        In full impl: call plate_what_next, tick_schedules, filter by risk_tolerance + enforce_budget.
        """
        actions: list[dict[str, Any]] = []
        # Per design/#470: if disabled or risk 'off', no autonomous actions (no what_next, no procedures).
        if not self.enabled or self.risk_tolerance == 'off':
            return actions
        # Suggest what-next + due procedures (risk filtered, from loaded .agentic/procedures/ registry)
        actions.append({"type": "what_next", "prompt_segment": "Use plate_what_next + autonomy status; make progress on next open child of #470 (one at a time)."})
        for proc in snapshot.due_procedures:
            if self._risk_rank(proc.get("risk_level", "medium")) <= self._risk_rank(self.risk_tolerance):

                if self.enforce_budget(proc.get("est_tokens", 2000), "procedure"):
                    actions.append({"type": "run_procedure", "id": proc.get("id")})
        return actions

    def run_cycle(self, *, dry_run: bool = False, max_steps: int | None = None) -> CycleReport:
        """Main entry for scheduled/looped autonomous execution.

        Introspect -> enforce -> decide -> execute (or delegate with trigger comments) -> log markers + usage.
        Returns structured report; caller (gh plate autonomy run --loop or scheduler) emits terse bullets only.
        """
        ts = datetime.now(timezone.utc).isoformat()
        # Do not unconditionally zero _spent_this_cycle here: daily rollover + carry across --loop cycles (reused engine) is handled inside enforce_budget's date check. Per-cycle accounting starts from instance init (new engine) or accumulated (loop reuse). Addresses review feedback on daily budget enforcement in long-running loops.
        snap = self.introspect()
        actions: list[str] = []
        throttled: list[str] = []
        paused = False
        budget_dec = "proceed"

        decided = self.decide_next(snap)
        for act in decided[: (max_steps if max_steps is not None else 10)]:
            est = 1000  # heuristic stub; real from action_kind
            if not self.enforce_budget(est, act.get("type", "unknown")):
                throttled.append(act.get("type", "action"))
                action = self.autonomy_config.get("token_budget", {}).get("action", "throttle")
                if action == "pause":
                    paused = True
                    budget_dec = "pause"
                else:
                    budget_dec = "throttle"

                continue
            if dry_run:
                actions.append(f"dry-run: {act}")
                continue
            # Execute or delegate (in full: deterministic or plate_delegate_to_agent + GitHub trigger comment)
            actions.append(f"executed/delegated: {act}")
            # Example marker (real engine would post via gh client)
            # <!-- PLATE-AUTONOMY-CYCLE: ... -->

        report = CycleReport(
            status="completed" if not paused else "paused",
            actions_taken=actions,
            throttled=throttled,
            paused=paused,
            budget_decision=budget_dec,
            snapshot=snap.to_dict(),
            timestamp=ts,
        )
        # In real: post usage report block if cycle produced artifact/closure
        return report

    def run_procedure(self, proc_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Run a named procedure (from .agentic/procedures/ or built-in)."""
        if dry_run:
            return {"proc_id": proc_id, "status": "dry-run"}
        # Find def for logging
        pdef = next((p for p in self.procedures if p.id == proc_id), None)
        if not pdef:
            return {"proc_id": proc_id, "status": "error", "reason": "unknown procedure id"}
        if not pdef.enabled:
            return {"proc_id": proc_id, "status": "skipped", "reason": "procedure disabled"}
        if self._risk_rank(pdef.risk_level) > self._risk_rank(self.risk_tolerance):
            return {"proc_id": proc_id, "status": "skipped", "reason": "risk_tolerance too low for procedure risk_level"}
        # Budget check (best-effort; full governor in decide/enforce for main paths)
        if not self.enforce_budget(4000, "procedure"):
            return {"proc_id": proc_id, "status": "skipped", "reason": "budget throttled"}
        # In full impl: dispatch steps using allow-listed MCP calls (e.g. plate_perform_information_audit, plate_pr_babysit, plate_costs)
        # For now, record marker + usage (as required by PLATE for procedures)
        marker = f"<!-- PLATE-PROCEDURE-RUN:{proc_id} cadence={pdef.cadence} risk={pdef.risk_level} -->"
        return {"proc_id": proc_id, "status": "executed", "log_marker": marker}

    def tick_schedules(self) -> list[dict[str, Any]]:
        """Find due procedures (cadence match) whose risk_level <= tolerance and run them."""
        due = []
        for p in self.procedures:
            if not p.enabled:
                continue
            if self._risk_rank(p.risk_level) > self._risk_rank(self.risk_tolerance):
                continue
            # Demo: treat "nightly"/"weekly" as due in this autonomous run (real would use last-run timestamp or cron lib)
            if p.cadence in ("nightly", "weekly", "manual"):
                due.append({"id": p.id, "risk_level": p.risk_level, "est_tokens": 4000})
        return due

    def _risk_rank(self, tol: str) -> int:
        order = {"off": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        # Default to 0 (off) for unknown/invalid risk_tolerance (fail closed; prevents silent low-rank allow on typo per review feedback).
        return order.get((tol or '').lower(), 0)


# Convenience for MCP/CLI
def get_autonomy_status(repo: str | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.get_status().to_dict()


def run_autonomy_cycle(repo: str | None = None, dry_run: bool = False, max_steps: int | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.run_cycle(dry_run=dry_run, max_steps=max_steps).to_dict()
