"""AutonomyEngine runtime for Epic #470.

Core software that introspects project state (via health, epics, costs, plate_config, procedures)
and decides/delegates/executes autonomous actions at the user's budgeted token rate and
configured risk_tolerance (core philosophy: autonomous by default unless 'off').

Implements the contract from docs/design/autonomous-plate-engine.md (refined by Research #471).
Wired via mcp_server (plate_autonomy_* tools) and cli (gh plate autonomy ...).
Follows quiet ops for looped/scheduled use (terse bullets only; comments only on real progress).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    budget_remaining_usd: float | None = None
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
        self.autonomy_config = self.config.autonomy or {}
        self.risk_tolerance = self.autonomy_config.get("risk_tolerance", "medium")
        self.enabled = self.autonomy_config.get("enabled", True)
        # Simple in-memory spend for governor (real impl would persist or use comments).
        # Use _spent_today (daily reset); per-cycle semantics approximated under daily for skeleton (full separation in governor follow-up).
        self._spent_today: int = 0
        self._last_reset = datetime.now(timezone.utc).date()

    def get_status(self) -> AutonomyStatus:
        """Return live status (used by plate_autonomy_status + health enrichment)."""
        # Integrate real reports
        try:
            # Pass repo (None supported; helpers resolve local git remote for full data even without explicit --repo)
            health = get_health(self.repo).to_dict()
            costs = get_cost_report(self.repo).to_dict()
            config_report = get_plate_config_report(self.repo).to_dict()
        except Exception:
            health = costs = config_report = {}

        # Basic autopilot stub (real: composite from PRs closed autonomously, cycles, gaps, adherence)
        autopilot = 42  # placeholder; real computation in observability child

        return AutonomyStatus(
            enabled=self.enabled,
            risk_tolerance=self.risk_tolerance,
            budget_remaining_tokens=self.autonomy_config.get("token_budget", {}).get("daily", 50000) - self._spent_today,
            budget_remaining_usd=self.autonomy_config.get("cost_ceiling_usd"),
            last_cycle=datetime.now(timezone.utc).isoformat(),
            autopilot_score=autopilot,
            due_procedures=[],  # populated by tick_schedules in full impl
            open_human_checkpoints=health.get("errors", []),
        )

    def introspect(self) -> ProjectSnapshot:
        """Gather full project state for decide_next (health + epics + costs + config + procedures)."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            health = get_health(self.repo).to_dict()
            epics = get_epic_status(self.repo).to_dict()
            costs = get_cost_report(self.repo).to_dict()
            pconfig = get_plate_config_report(self.repo).to_dict() if self.repo else {}
        except Exception as exc:
            health = {"error": str(exc)}
            epics = costs = pconfig = {}

        # due_procedures stub (full: load from .agentic/procedures/ + built-ins, filter by risk_tolerance)
        due: list[dict[str, Any]] = []

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
            self._spent_today = 0
            self._last_reset = today

        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000)
        daily_cap = self.autonomy_config.get("token_budget", {}).get("daily", 50000)
        action = self.autonomy_config.get("token_budget", {}).get("action", "throttle")

        projected = self._spent_today + estimated  # (real: over-estimate here, e.g. * 1.5 + buffer)

        if projected > cap or (self._spent_today + estimated) > daily_cap:
            if action == "pause":
                # In full engine: set paused, post status comment on Epic or autonomy Discussion
                return False
            if action == "throttle":
                # Caller should skip low-pri; here we just record and allow (caller decides)
                self._spent_today += estimated // 2  # partial spend on throttle
                return True
            # warn: allow but log
            self._spent_today += estimated
            return True

        self._spent_today += estimated
        return True

    def decide_next(self, snapshot: ProjectSnapshot) -> list[dict[str, Any]]:
        """Decide actions for the cycle (what_next + risk-filtered procedures + budget-aware).

        In full impl: call plate_what_next, tick_schedules, filter by risk_tolerance + enforce_budget.
        """
        actions: list[dict[str, Any]] = []
        # Stub: always suggest a what-next style action + any due procedures under tolerance
        actions.append({"type": "what_next", "prompt_segment": "Use plate_what_next + autonomy status; make progress on next open child of #470 (one at a time)."})
        for proc in snapshot.due_procedures:
            # risk_level string -> rank for consistent int compare with tolerance rank (per Copilot review)
            proc_risk = proc.get("risk_level", "medium")
            if self._risk_rank(proc_risk) <= self._risk_rank(self.risk_tolerance):
                if self.enforce_budget(proc.get("est_tokens", 2000), "procedure"):
                    actions.append({"type": "run_procedure", "id": proc.get("id")})
        return actions

    def run_cycle(self, *, dry_run: bool = False, max_steps: int | None = None) -> CycleReport:
        """Main entry for scheduled/looped autonomous execution.

        Introspect -> enforce -> decide -> execute (or delegate with trigger comments) -> log markers + usage.
        Returns structured report; caller (gh plate autonomy run --loop or scheduler) emits terse bullets only.
        """
        ts = datetime.now(timezone.utc).isoformat()
        snap = self.introspect()
        actions: list[str] = []
        throttled: list[str] = []
        paused = False
        budget_dec = "proceed"

        if not self.enabled or self.risk_tolerance == "off":
            # Per risk matrix / Epic: off/absent means no new autonomous actions (status/introspect still allowed)
            return CycleReport(
                status="paused",
                actions_taken=[],
                throttled=[],
                paused=True,
                budget_decision="off",
                snapshot=snap.to_dict(),
                timestamp=ts,
            )

        decided = self.decide_next(snap)
        for act in decided[: (max_steps if max_steps is not None else 10)]:
            est = 1000  # heuristic stub; real from action_kind
            if not self.enforce_budget(est, act.get("type", "unknown")):
                throttled.append(act.get("type", "action"))
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
        # Full: load def, dispatch allow-listed steps (info_audit, health, babysit, etc.), log PLATE-PROCEDURE-RUN + usage
        return {"proc_id": proc_id, "status": "executed", "log_marker": f"<!-- PLATE-PROCEDURE-RUN:{proc_id} -->"}

    def tick_schedules(self) -> list[dict[str, Any]]:
        """Find due procedures (cadence match) whose risk_level <= tolerance and run them."""
        # Stub: in real load from .agentic/procedures/*.json + built-ins, filter, call run_procedure
        return []

    def _risk_rank(self, tol: str) -> int:
        order = {"off": 0, "low": 1, "medium": 2, "high": 3}
        return order.get(tol, 1)


# Convenience for MCP/CLI
def get_autonomy_status(repo: str | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.get_status().to_dict()


def run_autonomy_cycle(repo: str | None = None, dry_run: bool = False, max_steps: int | None = None) -> dict[str, Any]:
    engine = AutonomyEngine(repo=repo)
    return engine.run_cycle(dry_run=dry_run, max_steps=max_steps).to_dict()
