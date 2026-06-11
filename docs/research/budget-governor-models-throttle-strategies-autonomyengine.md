# Budget Governor Models & Throttle Strategies for AutonomyEngine

- **Issue:** #471
- **Researched by:** Grok (via scheduled /loop autonomous execution for Epic #470)
- **Date:** 2026-06-11
- **Status:** Completed

## Research Question

How should the budget governor in the AutonomyEngine estimate costs of actions (e.g. before calling plate_perform_information_audit, large plan_epic, delegations, apply-mode procedures), decide on throttle/pause/warn actions when near/over daily/per-cycle caps, handle resume after reset, and expose observability? Integrate with existing costs.py harvesting + USAGE REPORTs. Provide models, heuristics, over-estimate policy, and how it feeds the engine contract (Design #472) and implementation (Feature #474 etc.).

## Sources

- Epic #470 and child #471 (planning consensus on governor as #1 prioritized love factor; "full governor in core"; "throttle or pause"; "before delegate/plan/audit"; risk matrix with off/absent = no new auto behavior)
- AGENTS.md (Quiet operations for long-running/looped agents: terse bullets only; resource consciousness; human checkpoints preserved; usage report blocks mandatory on closures for Feature/Question; atomic PR discipline)
- src/plate_core/costs.py (current post-hoc harvest of === USAGE REPORT === blocks from closed issues, UsageReport/CostReport dataclasses, harvest_usage_reports using GitHub search + comment parsing with regex for tokens/cost/duration, get_cost_report, format_cost_markdown; integrates with .agentic/COSTS.md and plates-on-issue-closed workflow)
- src/plate_core/plate_config.py (current schema for .plate pre-autonomy in this snapshot; load/resolve/validate/migration patterns; future token_budget/cost_ceiling planned)
- src/plate_core/mcp_server.py (current plate_costs tool exposure and plate_what_next; integration points for future governor calls before heavy tools; no plate_autonomy_* yet in this snapshot)
- .agentic/COSTS.md (current log is header-only; no historical data yet in this repo)
- Code search (grep for cost|token|budget|estimate|throttle|pause in src/plate_core): confirms costs only in reporting (mcp_server, costs.py); no pre-action estimation; "pause" only in blocking Question/contemplation context; agent_guidance emphasizes resource consciousness for autonomous runs
- Related design: docs/design/cost-control-*.md (prior layered context and thin surfaces for cost control)
- GitHub state (via MCP tools): #470 Epic + #471 open; PR 483 is the Documentation artifact for this research
- Search path documented: Started with GitHub MCP issue_read on #470 + sub-issues to confirm children and state. Used local read_file/grep on key sources (costs, config, mcp, AGENTS). Ran terminal git status. Cross-referenced prior cost-control designs and Epic body. No external web; all primary repo artifacts.

This research artifact itself (the .md) + the pseudocode sketch below serve as the detailed model for Design #472 and Feature #474 slices.

## Findings

Current cost system is purely **observability / post-facto**:
- Harvests only on closed Feature/Question issues via GitHub search for the USAGE REPORT marker (from AGENTS.md requirement).
- Parses with regex; aggregates totals per Epic or repo.
- No estimation before actions; no integration into what_next, decide, or run paths.
- .agentic/COSTS.md exists but empty in practice here.
- plate_costs MCP/CLI surface exists for reporting.

The design for AutonomyEngine explicitly calls for **pre-action governor**:
- `enforce_budget(estimated_tokens: int, action_kind: str)` called in decide_next and before expensive steps in run_cycle.
- On breach: "throttle" (skip low-priority procedures, force dry_run, increase sleep, prefer cheap paths), "pause" (stop cycle + status comment with resume info), or "warn".
- Caps: daily (UTC date reset), per_cycle.
- Resume: explicit --resume or next scheduled tick; record last_budget_reset.
- "Always over-estimate for safety."
- Estimation: "start with simple heuristics (tool name + scope + prior averages from costs reports)"; improve in this Research child.
- Real-time burn in plate_autonomy_status + health.
- Ties to risk_tolerance (governor still enforces even at high tolerance).

No dedicated *token budget* estimation or throttle logic yet in the AutonomyEngine or decide/run paths (grep confirmed; separate risk/timebox estimation surfaces exist elsewhere in plate_core for other purposes such as contemplation). "budget" and "throttle" appear only in planned config and design prose today.

Heuristics ideas (based on sources):
- Base cost by action/tool: e.g. plate_perform_information_audit (high, scans many surfaces + Goals + issues) ~ 5k-15k tokens; plate_health (low) ~ 200-500; full plan_epic child gen (medium-high, depends on # gaps); delegation (variable); apply-mode procedures (high if involves multiple MCP calls).
- Multipliers: + number of items (e.g. open issues count from health/epic_status, scope size); + historical avg from past reports for similar epic/label (even if sparse, use .agentic/COSTS.md or harvest); context size (current prompt length, but keep thin).
- Over-estimate: 1.5x-2x base + 20% buffer for safety; cap at per_cycle if known.
- Action policy: integrate with risk (at "off" skip governor or always throttle); priority queue for procedures (high risk_tolerance allows more before throttle).
- State: store last reset date + spent in memory or a lightweight .agentic/autonomy/budget.json (or GitHub comment/Discussion for durability); daily reset logic using datetime.
- Observability: include "budget_remaining_tokens", "burn_rate", "throttled_actions" in AutonomyStatus and health report; emit in quiet loop summaries.

Risks/edge cases from sources:
- Estimation inaccuracy (hence over-estimate + post-action actual harvest for calibration).
- Sparse historical data initially (fall back to static tables; improve over time via the costs system).
- Host agent variance (the governor estimates the *PLATE engine* portion; full host tokens are higher but outside scope per design).
- Resume after pause: the scheduler (/loop) or tick will re-invoke; engine should be idempotent.
- Ties to quiet ops: governor decisions must produce only terse bullets when in loop; no noisy comments unless real progress or checkpoint.

This research directly feeds the Design #472 (add estimate_cost helper to contract, update enforce_budget signature/decision type) and Feature #474 (implement in AutonomyEngine + wire into run_cycle/decide_next and MCP).

## Recommendation

1. Adopt a simple heuristic-based estimator in the AutonomyEngine (static base costs per known PLATE action + dynamic factors from health/epic_status + historical from costs harvest; always 1.5-2x over-estimate).
2. Implement enforce_budget that returns Decision (proceed | throttle | pause | warn) and updates internal spend tracking with daily reset.
3. Expose via plate_autonomy_status (budget fields) and enrich health.
4. Update the design doc (autonomous-plate-engine.md) if needed for the model details (this Research doc serves as the detailed artifact).
5. No SPEC.md change (this is internal engine detail, not product intent).
6. The implementing Feature PRs should reference this Research and close #471 via the Documentation PR that lands this .md file.

Next autonomous step: move to next sub-issue (#472 Design) once this Research is closed via its Documentation PR. No more autonomous progress possible on #471 without the implementation slices (which are separate children).

### Pseudocode / API Sketch for AutonomyEngine (for #472 Design / #474 impl lift)

```python
# Minimal sketch: AutonomyEngine governor (research #471 -> design #472)
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

Decision = Literal["proceed", "throttle", "pause", "warn"]

BASE_COSTS = {
    "plate_perform_information_audit": 8000,
    "plate_plan_epic": 6000,
    "plate_delegate_to_agent": 2500,
    "plate_health": 400,
    "plate_autonomy_run_cycle": 1500,
    # ... extend from costs harvest + observed
}

@dataclass
class BudgetState:
    last_reset: date
    spent_this_cycle: int = 0
    spent_today: int = 0

class AutonomyEngine:
    def __init__(self, config: dict):
        self.autonomy_config = config.get("autonomy", {})
        self._budget = BudgetState(last_reset=date.today())
        # daily = self.autonomy_config.get("token_budget", {}).get("daily", 50000)
        # per_cycle = ...

    def estimate_cost(self, action: str, context: dict) -> int:
        base = BASE_COSTS.get(action, 1000)
        # dynamic: open issues, epic gaps, context size (thin)
        mult = 1.0 + 0.05 * context.get("open_issues", 0)
        hist = context.get("historical_avg", 0)
        if hist:
            base = max(base, int(hist * 0.8))
        return int(base * mult * 1.7)  # 1.5-2x over-estimate safety

    def _reset_if_new_day(self):
        today = date.today()
        if self._budget.last_reset != today:
            self._budget.last_reset = today
            self._budget.spent_today = 0

    def enforce_budget(self, estimated: int, action: str) -> Decision:
        if not self.autonomy_config.get("enabled", True):
            return "proceed"
        self._reset_if_new_day()
        daily_cap = self.autonomy_config.get("token_budget", {}).get("daily", 50000)
        cycle_cap = self.autonomy_config.get("token_budget", {}).get("per_cycle", 8000)
        action_pref = self.autonomy_config.get("token_budget", {}).get("action", "throttle")

        projected_daily = self._budget.spent_today + estimated
        projected_cycle = self._budget.spent_this_cycle + estimated

        if projected_daily > daily_cap or projected_cycle > cycle_cap:
            if action_pref == "pause":
                return "pause"
            if action_pref == "warn":
                return "warn"
            return "throttle"  # default safe
        # charge (real impl may charge partial on throttle)
        self._budget.spent_today += estimated
        self._budget.spent_this_cycle += estimated
        return "proceed"

    # In run_cycle / decide_next:
    #   est = self.estimate_cost(proc["id"], snap.context)
    #   dec = self.enforce_budget(est, "run_procedure")
    #   if dec != "proceed": ... throttle/pause logic, record in report
```

This sketch is intentionally small and directly liftable; real impl will live in src/plate_core/autonomy.py with the existing dataclasses (AutonomyStatus, CycleReport) and wire to plate_config.

## Example Usage Report Block (reference only)

Actual reports are posted to issue/PR closure comments (for Feature/Question harvesting by plates-on-issue-closed + .agentic/COSTS.md). See AGENTS.md §Issue Artifact Rules.

```
=== USAGE REPORT ===
tokens: 0
cost: $0.00
duration: 00:05:00
=== END USAGE REPORT ===
```