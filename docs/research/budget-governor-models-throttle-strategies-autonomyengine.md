# Budget Governor Models & Throttle Strategies for AutonomyEngine

- **Issue:** #471
- **Researched by:** Grok (via scheduled /loop autonomous execution for Epic #470)
- **Date:** 2026-06-11
- **Status:** Completed

## Research Question

How should the budget governor in the AutonomyEngine estimate costs of actions (e.g. before calling plate_perform_information_audit, large plan_epic, delegations, apply-mode procedures), decide on throttle/pause/warn actions when near/over daily/per-cycle caps, handle resume after reset, and expose observability? Integrate with existing costs.py harvesting + USAGE REPORTs. Provide models, heuristics, over-estimate policy, and how it feeds the engine contract (Design #472) and implementation (Feature #474 etc.).

## Sources

- Epic #470 and child #473 (config schema + validation for autonomy section; risk matrix with off/absent = no new auto)
- Primary: docs/design/autonomous-plate-engine.md (the planning design artifact, sections on Token budget governor, AutonomyEngine runtime, risk matrix, enforcement in decide_next/run_cycle)
- AGENTS.md (Quiet operations for long-running/looped agents: terse bullets only; resource consciousness; human checkpoints preserved; usage report blocks mandatory on closures; atomic PR discipline)
- src/plate_core/costs.py (current post-hoc harvest of === USAGE REPORT === blocks from closed issues, UsageReport/CostReport dataclasses, harvest_usage_reports using GitHub search + comment parsing with regex for tokens/cost/duration, get_cost_report, format_cost_markdown; integrates with .agentic/COSTS.md and plates-on-issue-closed workflow)
- src/plate_core/plate_config.py (autonomy section added via PR 484 / v1.2 schema + deep validate for risk enum, token_budget numerics not-bool, bools for enabled/schedules, unknown keys at all levels, loop fields, migration 1.1->1.2; explicit .plate seed)
- src/plate_core/mcp_server.py (plate_costs tool exposure; plate_what_next, plate_autonomy_status and plate_autonomy_run_cycle MCP surfaces (skeleton + basic in PR 485 for #474); integration points for future governor calls before heavy tools)
- .agentic/COSTS.md (current log is header-only; no historical data yet in this repo)
- Code search (grep for cost|token|budget|estimate|throttle|pause in src/plate_core): confirms costs only in reporting (mcp_server, costs.py); no pre-action estimation; "pause" only in blocking Question/contemplation context; agent_guidance emphasizes resource consciousness for autonomous runs
- Related design: docs/design/cost-control-*.md (prior layered context and thin surfaces for cost control); docs/design/autonomous-plate-engine.md
- GitHub state (via MCP tools): #470 Epic + children (config #473 done via PR 484 Documentation; skeleton #474 / AutonomyEngine in PR 485; research #471; design #472); PR 485 is the Feature artifact for the engine skeleton + basic MCP surfaces (status, run_cycle).

Search path documented: Started with GitHub MCP issue_read on #470 + sub-issues to confirm children and state. Used local read_file/grep on key sources (plate_config, costs, AGENTS, mcp, design, autonomy). Ran terminal git status, fetch, rebase. Cross-referenced prior cost-control designs, Epic body, sibling PRs (484 config, 485 skeleton). No external web; all primary repo artifacts.

This research + the config slice (PR 484) + skeleton + MCP surfaces (PR 485) + sibling Design #472 provide the models for AutonomyEngine governor.

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

No existing estimation logic in the codebase (grep confirmed zero "estimate", "throttle" only in design comments, "budget" only in planned config).

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
4. Update the design doc (docs/design/autonomous-plate-engine.md from #472 / PR 494) if needed for the model details (this Research doc serves as the detailed artifact).
5. No SPEC.md change (this is internal engine detail, not product intent).
6. The implementing Feature PRs should reference this Research and close #471 via the Documentation PR that lands this .md file.

Next autonomous step: move to next sub-issue (#472 Design) once this Research is closed via its Documentation PR. No more autonomous progress possible on #471 without the implementation slices (which are separate children).

## Example Usage Report Block (reference only)

Actual reports are posted to issue/PR closure comments (for Feature/Question harvesting by plates-on-issue-closed + .agentic/COSTS.md). See AGENTS.md §Issue Artifact Rules.

```
=== USAGE REPORT ===
tokens: 0
cost: $0.00
duration: 00:05:00
=== END USAGE REPORT ===
```
