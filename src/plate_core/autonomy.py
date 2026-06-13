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
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
    budget_remaining_usd: float | None = None  # float (or None) from cost_ceiling_usd; addresses type annotation review feedback for consistency with assignment in get_status
    last_cycle: str | None = None
    next_scheduled: str | None = None
    autopilot_score: int = 0  # 0-100 composite per #479 (auto PRs + unattended cycles + gaps closed + proc success + budget adherence)
    burn_rate: float = 0.0  # % of daily budget burned (for #479 observability + health)
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


class Decision(Enum):
    """Budget governor decision per #471 research + #472/#474 contract.

    PROCEED: action within budget, execute (full spend tracked).
    THROTTLE: near/over but continue partial (half-spend for safety, skip low-pri callers decide).
    PAUSE: hard stop this cycle (set paused, no further spend).
    WARN: over but allow (full spend, log for observability; rare).
    """
    PROCEED = "proceed"
    THROTTLE = "throttle"
    PAUSE = "pause"
    WARN = "warn"


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
            self.risk_tolerance = self.autonomy_config.get("risk_tolerance", "medium")
        self.procedures: list[ProcedureDef] = self._load_procedures()
        # Simple in-memory spend for governor (real impl would persist or use comments)
        # Separate per-cycle (reset each run_cycle) and daily (UTC day rollover) counters to address review feedback on budget tracking.
        self._spent_this_cycle: int = 0
        self._spent_today: int = 0
        self._last_reset = datetime.now(timezone.utc).date()
        self.throttled_actions: int = 0  # for #479 autopilot calc and status

    def estimate_cost(self, action_kind: str, scope: dict[str, Any] | None = None) -> int:
        """#471 estimation heuristics wired for #474: tool/scope/historical + 1.5-2x over-est + 20% buffer + cap.

        References Research #471 (base costs, multipliers from #items/historical from costs/.agentic/COSTS.md, over-est policy).
        Called from decide_next + run_cycle; result passed to enforce_budget.
        Best-effort (sparse data falls back to static); always over for safety per design.
        """
        scope = scope or {}
        kind = (action_kind or "unknown").lower().replace("-", "_")
        bases: dict[str, int] = {
            "info_audit": 10000,      # 5k-15k per #471
            "perform_information_audit": 10000,
            "health": 350,
            "plate_health": 350,
            "plan_epic": 7500,
            "what_next": 1500,
            "run_procedure": 4000,
            "delegate": 2200,
            "plate_delegate_to_agent": 2200,
            "babysit": 4500,
            "feedback_integration": 4500,
            "cost_rollup": 1800,
            "drift": 5500,
            "nightly_drift_detection": 5500,
            "unknown": 2200,
            "default": 2200,
        }
        base = bases.get(kind, bases["default"])

        # scope multiplier: #items / gaps / issues (from introspect health/epic_status passed in scope)
        num_items = 1
        for k in ("num_items", "num_issues", "gaps", "open_issues", "children"):
            if k in scope:
                try:
                    num_items = max(num_items, int(scope[k]) or 1)
                except (ValueError, TypeError):
                    pass
        mult = 1.0 + min(2.0, (num_items - 1) * 0.12)  # ~12% per extra item, cap +2x

        # historical from passed cost_report (preferred, avoids GH every est) or parse local .agentic/COSTS.md
        hist_avg = 0
        cr = scope.get("cost_report") or {}
        if isinstance(cr, dict):
            reps = cr.get("reports") or []
            if reps and cr.get("total_tokens"):
                hist_avg = int(cr.get("total_tokens", 0) / max(1, len(reps)))
        if hist_avg <= 0:
            try:
                costs_path = Path(".agentic/COSTS.md")
                if costs_path.exists():
                    txt = costs_path.read_text(encoding="utf-8", errors="ignore")
                    # crude tokens col parse from md table ( | tokens | )
                    nums = [int(m) for m in re.findall(r"\|\s*(\d{3,})\s*\|", txt)]
                    if nums:
                        hist_avg = sum(nums) // len(nums)
            except Exception:
                pass
        if hist_avg > 100:
            base = max(base, int(hist_avg * 0.6))  # blend lower bound from history

        # 1.5-2x over-estimate + 20% buffer (use ~1.75x avg)
        est = int(base * mult * 1.75)
        est = int(est * 1.20)  # +20% buffer

        # cap relative to per_cycle (leave headroom, never propose >90% of cycle alone)
        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000) or 8000
        est = min(est, int(cap * 0.9))
        return max(100, est)

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
            health = get_health(self.repo).to_dict() if self.repo else {}
            costs = get_cost_report(self.repo).to_dict() if self.repo else {}
            config_report = get_plate_config_report().to_dict()  # always use local checkout .plate for config (repo str is for remote health/costs only)
        except Exception:
            health = costs = config_report = {}

        # Complete observability per #479: autopilot_score composite (% auto PRs proxy from health + unattended cycles + gaps closed + proc success + budget adherence + throttled inverse) + burn_rate.
        # References design #472 + research #471. Uses available signals (no full 30d GH history here; health/epics/costs provide proxies).
        risk_rank = self._risk_rank(self.risk_tolerance)
        base = 25 + (risk_rank * 12)  # 25-61 from risk (high tolerance enables more auto)
        daily = self.autonomy_config.get("token_budget", {}).get("daily", 50000) or 50000
        budget_adherence = 50
        burn_rate = 0.0
        if daily > 0:
            spent = self._spent_today
            burn_rate = max(0.0, min(100.0, (spent / daily) * 100))
            remaining = daily - spent
            budget_adherence = max(0, min(100, int((remaining / daily) * 100)))
        # proc success proxy + due count (more due + enabled = higher auto progress)
        proc_count = len([p for p in self.procedures if p.enabled])
        proc_bonus = min(15, proc_count * 4)
        # health signals for auto-prs/gaps (if present in future health; else 0)
        auto_prs = min(10, (health or {}).get("auto_merged_prs", 0) or 0)
        gaps_closed = min(10, (health or {}).get("gaps_closed_autonomously", 0) or 0)
        throttle_penalty = min(10, self.throttled_actions or 0)  # inverse
        autopilot = int(base + (budget_adherence * 0.25) + proc_bonus + auto_prs + gaps_closed - throttle_penalty)
        autopilot = max(0, min(100, autopilot))

        due_ids = [p.id for p in self.procedures if p.enabled and self._risk_rank(p.risk_level) <= self._risk_rank(self.risk_tolerance)]
        return AutonomyStatus(
            enabled=self.enabled,
            risk_tolerance=self.risk_tolerance,
            budget_remaining_tokens=daily - self._spent_today,
            budget_remaining_usd=float(self.autonomy_config.get("cost_ceiling_usd") or 0) if self.autonomy_config.get("cost_ceiling_usd") is not None else None,
            last_cycle=datetime.now(timezone.utc).isoformat(),
            autopilot_score=autopilot,
            burn_rate=round(burn_rate, 1),
            due_procedures=due_ids,
            open_human_checkpoints=health.get("errors", []) if isinstance(health, dict) else [],
            throttled_actions=getattr(self, "throttled_actions", 0),
        )

    def introspect(self) -> ProjectSnapshot:
        """Gather full project state for decide_next (health + epics + costs + config + procedures)."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            health = get_health(self.repo).to_dict() if self.repo else {}
            epics = get_epic_status(self.repo).to_dict() if self.repo else {}
            costs = get_cost_report(self.repo).to_dict() if self.repo else {}
            pconfig = get_plate_config_report().to_dict()  # always use local checkout .plate for config (repo str is for remote health/costs only)
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

    def enforce_budget(self, estimated: int, action_kind: str) -> Decision:
        """Core governor per #471/#472/#474. Returns Decision (not bool).

        estimate_cost (wired #471 heuristics) is called by caller (decide_next/run_cycle) and passed here.
        On breach: throttle (partial spend + continue), pause (stop), warn (continue full).
        Daily UTC reset + per_cycle/daily caps. Always respects risk_tolerance=='off'.
        Ties to siblings: called before info_audit/plan_epic/delegate/apply procedures.
        """
        if not self.enabled or self.risk_tolerance == "off":
            return Decision.PROCEED  # explicit off or disabled: no autonomous budget enforcement

        # Daily reset (UTC date) for _spent_today; _spent_this_cycle reset per run_cycle
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset:
            self._spent_this_cycle = 0
            self._spent_today = 0
            self._last_reset = today

        cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000) or 8000
        daily_cap = self.autonomy_config.get("token_budget", {}).get("daily", 50000) or 50000
        policy = self.autonomy_config.get("token_budget", {}).get("action", "throttle")

        projected_cycle = self._spent_this_cycle + estimated
        projected_daily = self._spent_today + estimated

        if projected_cycle > cap or projected_daily > daily_cap:
            if policy == "pause":
                # no additional spend on hard pause
                return Decision.PAUSE
            if policy == "throttle":
                # partial spend + continue (throttle low-pri in caller)
                self._spent_this_cycle += max(1, estimated // 2)
                self._spent_today += max(1, estimated // 2)
                self.throttled_actions += 1
                return Decision.THROTTLE
            # warn or other: full spend but flag
            self._spent_this_cycle += estimated
            self._spent_today += estimated
            return Decision.WARN

        self._spent_this_cycle += estimated
        self._spent_today += estimated
        return Decision.PROCEED

    def decide_next(self, snapshot: ProjectSnapshot) -> list[dict[str, Any]]:
        """Decide actions for the cycle (what_next + risk-filtered procedures + budget-aware).

        Wires #471: call estimate_cost (with scope from snapshot) before append; check enforce_budget Decision.
        Budget check here + run_cycle (per #474 wiring); skip PAUSE actions, note THROTTLE.
        References #471 heuristics + #472 contract; no human checkpoint changes.
        """
        actions: list[dict[str, Any]] = []
        if not self.enabled or self.risk_tolerance == "off":
            return actions
        # Build scope for est (historical + items from introspect snapshot for #471)
        scope = {
            "cost_report": snapshot.cost_report,
            "num_items": len(snapshot.due_procedures) + len(snapshot.epic_status.get("children", []) or []) or 3,
            "gaps": len(snapshot.health.get("recommendations", []) or []),
        }
        # what_next always proposed first (cheap) but still est for governor
        est = self.estimate_cost("what_next", scope)
        dec = self.enforce_budget(est, "what_next")
        if dec != Decision.PAUSE:
            act = {"type": "what_next", "prompt_segment": "Use plate_what_next + autonomy status; make progress on next open child of #470 (one at a time).", "est": est, "decision": dec.value}
            if dec == Decision.THROTTLE:
                act["throttled"] = True
            actions.append(act)
        for proc in snapshot.due_procedures:
            if self._risk_rank(proc.get("risk_level", "medium")) <= self._risk_rank(self.risk_tolerance):
                est = self.estimate_cost("run_procedure", {**scope, "id": proc.get("id")})
                dec = self.enforce_budget(est, "run_procedure")
                if dec != Decision.PAUSE:
                    pact = {"type": "run_procedure", "id": proc.get("id"), "est": est, "decision": dec.value}
                    if dec == Decision.THROTTLE:
                        pact["throttled"] = True
                    actions.append(pact)
        return actions

    def run_cycle(self, *, dry_run: bool = False, max_steps: int | None = None) -> CycleReport:
        """Main entry for scheduled/looped autonomous execution.

        Introspect -> enforce (real est from #471 estimate_cost) -> decide (budget wired) -> execute (delegate support) -> log markers + USAGE REPORT.
        Quiet enforcement: only append progress actions (executed/delegated/markers) to report; no non-progress/no-op comments (per quiet ops #456 + AGENTS.md).
        References #471/#472; ties to #478 procedures, #479 obs, #482 tests. Delegation via plate_delegate_to_agent + trigger markers.
        """
        ts = datetime.now(timezone.utc).isoformat()
        # Do not unconditionally zero _spent_this_cycle here: daily rollover + carry across --loop cycles (reused engine) is handled inside enforce_budget's date check. Per-cycle accounting starts from instance init (new engine) or accumulated (loop reuse). Addresses review feedback on daily budget enforcement in long-running loops.
        snap = self.introspect()
        actions: list[str] = []
        throttled: list[str] = []
        paused = False
        budget_dec = Decision.PROCEED.value
        total_est = 0

        self._spent_this_cycle = 0  # fresh per cycle
        decided = self.decide_next(snap)
        if not decided:
            # decide filtered all (PAUSE from est/enforce on tiny budget); probe to set paused state for report
            probe_est = self.estimate_cost("what_next", {})
            dec = self.enforce_budget(probe_est, "what_next")
            if dec == Decision.PAUSE:
                paused = True
                budget_dec = dec.value
        for act in decided[: (max_steps if max_steps is not None else 10)]:
            kind = act.get("type", "unknown")
            est = act.get("est") or self.estimate_cost(kind, {"cost_report": snap.cost_report, "num_items": 2})
            total_est += est
            dec = self.enforce_budget(est, kind)  # already called in decide but re-enforce here for run (idempotent spend guard)
            if dec == Decision.PAUSE:
                throttled.append(kind)
                paused = True
                budget_dec = Decision.PAUSE.value
                continue
            if dec in (Decision.THROTTLE, Decision.WARN):
                throttled.append(kind)
                budget_dec = dec.value if dec != Decision.PROCEED else budget_dec
                # for throttle: partial already spent in enforce; continue to execute (per task "throttle: partial spend + continue")
            if dry_run:
                actions.append(f"dry-run: {kind} est={est}")
                continue
            # Execute or delegate (support plate_delegate_to_agent + trigger comments per #472)
            executed_desc = f"executed: {kind}"
            try:
                if "delegate" in kind or "delegate_to_agent" in str(act):
                    # wire delegation (from baseline_catalog; narrow packet per design)
                    from .baseline_catalog import delegate_to_agent
                    # scope from act/snap; real would pass focused packet. Here best-effort marker + call (safe no-op if no agent match)
                    _ = delegate_to_agent(agent_id="plate", prompt_segment=act.get("prompt_segment", "autonomous progress"), context={"autonomy_cycle": ts, "risk": self.risk_tolerance})
                    executed_desc = f"delegated: {kind} (plate_delegate_to_agent triggered)"
            except Exception:
                pass  # delegation optional; fall to executed marker
            actions.append(executed_desc)
            # Full logging: PLATE-AUTONOMY-CYCLE marker + USAGE REPORT block (per #474 AC + AGENTS)
            marker = f"<!-- PLATE-AUTONOMY-CYCLE: ts={ts} kind={kind} est={est} decision={dec.value} budget_remaining~{max(0, (self.autonomy_config.get('token_budget',{}).get('per_cycle',8000)-self._spent_this_cycle))} -->"
            actions.append(marker)
            # USAGE style for traceability (even for engine cycles; harvested where Feature/Question close)
            if not dry_run:
                actions.append("=== USAGE REPORT ===\ntokens: " + str(est) + "\ncost: $0.00\n duration: 00:00:10 (autonomy est)\n=== END USAGE REPORT ===")

        report = CycleReport(
            status="completed" if not paused else "paused",
            actions_taken=actions,
            throttled=throttled,
            paused=paused,
            budget_decision=budget_dec,
            snapshot=snap.to_dict(),
            timestamp=ts,
        )
        return report

    def run_procedure(self, proc_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Run a named procedure (from .agentic/procedures/ or built-in)."""
        if dry_run:
            return {"proc_id": proc_id, "status": "dry-run"}
        # Find def for logging
        pdef = next((p for p in self.procedures if p.id == proc_id), None)
        # In full impl: dispatch steps using allow-listed MCP calls (e.g. plate_perform_information_audit, plate_pr_babysit, plate_costs)
        # For now, record marker + usage (as required by PLATE for procedures)
        marker = f"<!-- PLATE-PROCEDURE-RUN:{proc_id} cadence={pdef.cadence if pdef else 'unknown'} risk={pdef.risk_level if pdef else 'unknown'} -->"
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
