# Autonomous PLATE Engine & Scheduled Procedures — Design Spec

- **Issue:** #470 (https://github.com/akasper/plate/issues/470) — created in this interactive planning session
- **Designed by:** Grok (xAI) via interactive TUI Q&A planning session with user (full consensus captured in the Epic body and this doc)
- **Date:** 2026-06 (planning session)
- **Status:** Draft

## Problem

PLATE's core promise is "humans keep judgment, agents do the toil." Current autonomy is partial and fragmented:

- Binary `.github/AUTONOMOUS_MODE` file + `risk:low` label + `auto-merge` label + workflow for lightweight PRs only.
- Excellent introspection surfaces (`plate_health`, `plate_what_next`, `plate_epic_status`, `plate_costs`, `plate_perform_information_audit`) and drivers (`ContemplationEngine`, babysit, quiet-operations guidance) but no single "core engine" that ties them into continuous, budgeted, long-running operation.
- `plate_what_next` (v1) and the state-machine catalog in `docs/design/what-next-mcp-state-machine-catalog.md` (Epic #282) describe the autonomous implementation story, but the orchestrator remains stubby (see `.github/workflows/plates-agentic-orchestrator.yml` and MCP `_plan_epic_stub` / heuristic `_what_next`).
- Token/cost visibility exists (`plate_costs`, USAGE REPORT harvesting, Epic #265) but no governor that *prevents* overspend during long unattended runs.
- No first-class notion of recurring/scheduled procedures (audits, drift detection, maintenance, feedback integration) that users can declaratively enable at a chosen risk tolerance.
- `plate_plan_epic` is a stub; large Epics like this one still require heavy interactive toil.
- `.plate` config is mature (extensions, release, methodology, migrations) but has no `autonomy` section for the single "low-touch" knob users expect.

The result: PLATE can be driven autonomously *today* with host loops (`/loop`, babysit watch, Grok scheduler tools) + the plate persona + MCP tools, but it is not *self-driving* at the user's budgeted token rate for very long periods with graduated risk tolerance and built-in recurring work. This Epic is the heart of the PLATE vision — turning the methodology + core software into a reliable, observable, low-touch autonomous engine that users love.

## Vision (from interactive planning)

- User sets `risk_tolerance` (`low`/`medium`/`high`) + token budgets in `.plate`.
- High tolerance + sufficient budget → the repo "just runs": PRs auto-merge up to the allowed risk, scheduled procedures (nightly drift+audit+cleanup, etc.) execute, gaps become Questions or child stubs, feedback is integrated, all with full GitHub audit trail and quiet operation.
- The **AutonomyEngine** (new first-class runtime in `plate_core`) is the software that introspects project state and delegates (or executes deterministic steps).
- Everything respects a hard/soft budget governor so runs can continue for hours/days at the user's chosen rate.
- New procedure class (data-driven in `.agentic/procedures/`) for hourly/nightly/weekly/monthly/quarterly work.
- Migration from the legacy `.github/AUTONOMOUS_MODE` marker file (sunset as part of this Epic) to declarative control in `.plate`. Autonomous behavior is now the core default philosophy of PLATE (enabled unless `autonomy.risk_tolerance: "off"`). The marker file is no longer the signal; `.plate` is the single, human-readable source.
- MCP + CLI surfaces (`gh plate autonomy run --loop`) so host schedulers (Grok TUI `scheduler_create`, `/loop`, Copilot equivalents) can drive persistent execution.
- Observability: `autopilot_score`, burn rate, procedure run logs (PLATE-PROCEDURE-RUN markers + usage blocks), health integration.

## Constraints

- Never weaken existing human checkpoints (Task rules, `need:human-review`, critical-risk items, AGENTS.md/SPEC/credential/workflow changes, release ceremony human gates).
- GitHub remains the single source of truth; all decisions, runs, and artifacts produce inspectable comments, labels, issues, or files (no hidden external state).
- MCP surfaces stay stateless (engine state lives in GitHub + local .plate + .agentic/ + costs reports).
- Preserve atomic PR discipline, quiet-operations rules (terse bullets in loops, comments only on real progress or defined checkpoints), and resource consciousness.
- Rollout via fragments (`.agentic/releases/unreleased/`), template payload, and normal PLATE ceremonies. Clear migration path for repos using the legacy `.github/AUTONOMOUS_MODE` marker file (health/config surfaces will suggest adding the `.plate` autonomy section; the file itself can be deleted once migrated). Risk labels remain unchanged.
- Budget enforcement is best-effort + observable (cost estimation is approximate; governor can force dry-run / skip / pause but cannot perfectly predict host agent token use).
- Extensions can contribute procedures and autonomy behaviors (consistent with existing extension model).

## Design Decision

### 1. .plate autonomy section (config surface)

Add to schema (plate_config.py + DEFAULT_CONFIG + validation/migration):

```json
{
  "autonomy": {
    "enabled": true,
    "risk_tolerance": "medium",
    "token_budget": {
      "daily": 50000,
      "per_cycle": 8000,
      "action": "throttle"
    },
    "cost_ceiling_usd": 10.0,
    "schedules_enabled": true,
    "loop": {
      "default_sleep_seconds": 300,
      "max_cycles": null
    }
  }
}
```

- `risk_tolerance`: "off" | "low" | "medium" | "high". Controls which labeled work and procedures may proceed autonomously.
- Default behavior (new philosophy): when the `autonomy` section is present (or resolved via defaults/extensions), autonomous features are active at the configured `risk_tolerance` level. "off" explicitly disables (fully manual, no auto-merge, no auto-apply in babysit, no scheduled procedures, etc.). 
- Legacy migration: During transition, if `.github/AUTONOMOUS_MODE` is present but no `autonomy` section exists in `.plate`, the config report / health will emit migration guidance (recommend adding the section, typically starting at "low" or "medium" to match prior behavior). The generalized auto-merge and engine code will prefer `.plate` and can fall back or warn on the marker file for one release cycle before the file is fully ignored/removed from template expectations.
- Health report and `plate_config_get` surface the effective autonomy settings.
- Migration path from 1.1 → next version (similar to prior release/extensions migrations).

### 2. Risk tolerance matrix (MVP, adopted exactly from planning)

| Tolerance | Auto-merge PRs | Babysit auto-apply | Audits / drift | plan_epic auto-stubs | Scheduled procedures | Delegation scope | Notes |
|-----------|----------------|--------------------|----------------|----------------------|----------------------|------------------|-------|
| off | None (manual) | None (manual review) | dry_run default | Never | None (manual only) | Standard | Explicit disable of autonomous features. This replaces the old need for deleting the AUTONOMOUS_MODE marker file. |
| low | risk:low (config-driven; guards still apply) | Safe suggestions only | dry_run default | Explicit only | Only if declared risk:low | Standard + quiet loops | Entry-level autonomous; equivalent to old "AUTONOMOUS_MODE present + risk:low" but now expressed in .plate |
| medium | risk:low + risk:medium | Medium-safe + thread resolve | apply ok for medium | Limited (high-confidence only) | Procedures <= medium | Broader autonomous agents | Balanced default for most teams |
| high | risk:low/medium/high (never critical) | Broad (still respect suggestion safety) | apply for non-critical | Yes, from Goals + audit (stubs carry need:refinement) | Procedures <= high | Full (within budget) | "Low touch" single-knob experience |

**Critical always human:** Any change touching AGENTS.md, SPEC.md, .github/CODEOWNERS/workflows, credentials/secrets/auth, or carrying `risk:critical` or `need:human-review` requires explicit human action (Task or review). Governor and risk checks are enforced in `enforce_budget` + `decide_next`.

### 3. Token budget governor (full core enforcement)

- `costs.py` + harvest logic is the source of truth for spend.
- AutonomyEngine (and what_next / decide_next) call a new `enforce_budget(estimated_tokens: int, action: str) -> Decision` before expensive steps (full info_audit, large plan_epic child gen, certain delegations, apply-mode procedures).
- On near/over: "throttle" (skip low-pri procedures, force dry_run on audits, increase sleep, prefer cheap what_next paths), "pause" (stop cycle, post status comment with resume instructions), or "warn" (continue but log loudly).
- `per_cycle` and `daily` caps in config. Daily resets on UTC date change (or GitHub event).
- Real-time burn exposed in `plate_autonomy_status` and health.
- Resume: explicit `gh plate autonomy run --resume` or next scheduled tick after reset; engine records last_budget_reset.
- Estimation: start with simple heuristics (tool name + scope + prior averages from costs reports); improve in Research child. Always over-estimate for safety.

### 4. First-class AutonomyEngine runtime

New `src/plate_core/autonomy.py` (orchestrator.py) with:

```python
@dataclass
class AutonomyStatus: ...
@dataclass
class ProjectSnapshot: ...
@dataclass
class CycleReport: ...
@dataclass
class ProcedureDef: ...

class AutonomyEngine:
    def __init__(self, plate_config: PlateConfig, gh_client=None): ...
    def get_status(self) -> AutonomyStatus: ...
    def introspect(self) -> ProjectSnapshot: ...
    def enforce_budget(self, estimated: int, action_kind: str) -> bool: ...
    def decide_next(self, snapshot: ProjectSnapshot) -> list[Action]: ...
    def run_cycle(self, *, dry_run: bool = False, max_steps: int | None = None) -> CycleReport: ...
    def run_procedure(self, proc_id: str, *, dry_run: bool = False) -> ProcedureRunReport: ...
    def tick_schedules(self) -> list[ProcedureRunReport]: ...
    # helpers for host loop integration
```

- `run_cycle`: introspect → enforce → decide (what_next + due procedures filtered by risk + budget) → execute (deterministic steps or `plate_delegate_to_agent` + trigger comments for host agents, e.g. babysit-style `@copilot` or plate-specific markers) → record PLATE-AUTONOMY-CYCLE / PLATE-PROCEDURE-RUN markers + usage blocks → return structured report.
- Deterministic steps (contemplation, certain audits with apply, babysit thread resolution, branch cleanup, fragment aggregation prep) execute directly via core/MCP dispatch allow-list.
- Delegation steps post narrow, auditable trigger comments (building on babysit + discussions Ideas category for inter-agent logs per #287 etc.).
- Quiet rules: when called from a host loop, the engine's own turn summaries are terse bullets; only real artifacts or checkpoints produce GitHub comments.
- State machine catalog (#282) becomes executable: the engine is the canonical implementation of the "orchestrator" node and many transition actions.

MCP tools (registered in mcp_server.py):
- `plate_autonomy_status`
- `plate_autonomy_run_cycle` (supports dry_run, max_steps)
- `plate_autonomy_list_procedures`
- `plate_autonomy_run_procedure`
- (future) `plate_autonomy_pause`, `plate_autonomy_set_budget_override` (temporary, logged)

CLI (`cli.py`): `gh plate autonomy status|run|loop --loop --max-cycles N --dry-run --budget-override ...`

`gh plate autonomy run --loop` implements the persistent driver: read config, instantiate engine, while within budget and no external stop: report = engine.run_cycle(); emit terse bullet summary; sleep(configured or host-provided jitter).

Host integration: Grok TUI scheduler tools, `/loop`, Copilot equivalents simply invoke the CLI or MCP in their cadence. No host changes required for basic use.

### 5. Data-driven procedures (new .agentic/procedures/)

Directory + files (parallel to unreleased fragments):

`.agentic/procedures/nightly-drift-detection.json` (or .yml):

```json
{
  "id": "nightly-drift-detection",
  "cadence": "nightly",
  "risk_level": "medium",
  "description": "Compare live labels, wiki/Goals, .agentic/ fragments, health, and .plate against expected; surface drift as Audit or Question issues.",
  "steps": [
    {"tool": "plate_perform_information_audit", "args": {"scope": "repo", "dry_run": false}, "apply_if_risk_ok": true},
    {"tool": "plate_health", "args": {}},
    {"action": "compare_and_propose_drift_issues"}
  ],
  "log_to": ".agentic/autonomy/runs/",
  "max_tokens_per_run": 12000,
  "enabled": true,
  "requires": ["goals_page_present"]
}
```

Built-ins (MVP, shipped in core/template): nightly-drift-detection, nightly-info-audit, feedback-integration (babysit-all for PLATE_PR_FEEDBACK_AGENTS), cost-rollup, release-readiness-scan, stale-branch-cleanup, goals-refresh, binary-hygiene-audit, contemplation-backlog-sweep.

Engine `tick_schedules` (called from run_cycle or dedicated scheduled tick): enumerate due procedures (simple "nightly" resolution or cronparse for advanced), filter by risk_tolerance, execute via allow-listed dispatch, record markers + costs, write run log.

Users add/override in their repo; extensions can contribute via the existing extension manifest + .plate.installed mechanism (new contribution key allowed under the autonomy extension rules).

Logging: every run appends a structured `<!-- PLATE-PROCEDURE-RUN:BEGIN ... -->` comment (on a standing "Autonomy" Discussion in Ideas, on the Epic, or in `.agentic/autonomy/runs/<date>-<id>.md` committed on next human PR or by a maintenance procedure). Always includes usage block.

### 6. Observability & "users love it" surfaces

- `autopilot_score` (0-100): composite of % PRs auto-merged (last 30d), unattended cycles run without escalation, gaps closed autonomously vs manually, procedure success rate, budget adherence.
- `plate_autonomy_status` + health enrichment: current tolerance, budget remaining (tokens + $), last 5 cycles/procedures, next due, open human checkpoints, recent autopilot score trend.
- `.agentic/autonomy/` (or Discussions) for run history.
- Wiki snippet (optional Goals or new Autonomy page) surfaced by health.
- Cost burn rate and "at budget" warnings are first-class in status.

These directly address the prioritized love factors: budget governor visible, single risk knob, magical recurring procedures, visible autopilot %.

### 7. Integration & evolution points

- Evolves (does not replace) `plate_what_next`, ContemplationEngine, information audit, babysit, release status, etc. Engine calls them.
- `plates-agentic-orchestrator.yml` (stub) can be enhanced to call the new engine on issue events or schedule.
- plate persona / agent_guidance.py: add "Autonomy / long-running loops" section (already strong quiet rules); default routing prefers `plate_autonomy_status` + `plate_what_next`.
- State machine catalog becomes the executable spec for decide_next / run_cycle.
- `plate_plan_epic` (currently stub) gets real implementation; at high tolerance it can auto-propose many child stubs from Goals + latest audit (all marked need:refinement + provenance).
- Release ceremony, Epic-close, etc. can have autonomous prep steps (e.g. release-readiness-scan procedure) while human gates remain.

### 8. Safety, rollback, human override

- Any engine action that would touch forbidden areas is rejected with `need:human-review` + blocking comment.
- `--dry-run` / `dry_run=true` always available and default for lower tolerances.
- Manual pause / disable: set `autonomy.risk_tolerance: "off"` in `.plate` (or temporarily via a `PLATE-AUTONOMY-PAUSE` marker comment that the engine and health respect). The legacy marker file is no longer used for this.
- All changes are atomic PRs or clearly logged comments; squash-merge + revert is the escape hatch.
- Usage reports mandatory on any closure or major artifact the engine helps produce.

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Keep everything in persona prose + host scheduler only (no new core AutonomyEngine) | Violates the explicit request for "core software that introspects on project state and delegates to agents"; misses budget governor and first-class procedures. |
| Full external daemon or new hosted service | Breaks "GitHub is the single source of truth" and "lightweight / no new external services" constraints. |
| Allow-list every possible MCP call for procedures without risk gating | Too dangerous; would let high-tolerance users accidentally run destructive or high-cost things. |
| Replace risk:* labels with only config | Labels are stable metadata and already used in templates/workflows; config + labels together is the right split. |
| Hard real-time cron inside plate-core | MCP/CLI are the portable surfaces; host schedulers + GitHub scheduled workflows are the right triggers. Engine provides the "what to do" and "can I afford it". |

## Artifact

- This design doc (`docs/design/autonomous-plate-engine.md`).
- `.plate` schema + example in template payload.
- `src/plate_core/autonomy.py` (engine), updates to `plate_config.py`, `mcp_server.py`, `cli.py`, `pr_babysit.py`, `health.py`, `costs.py`, `agent_guidance.py`.
- `.agentic/procedures/` examples + built-in defs (in core data or template).
- New MCP tools + CLI commands.
- Updates to AGENTS.md (work loops, autonomous mode section, quiet ops), plugin/agents/plate.agent.md, baseline catalog, `.github/workflows/*` (generalized auto-merge, orchestrator), labels/docs, health signals.
- Per-feature fragments in `.agentic/releases/unreleased/` for every process/config change.
- Tests (unit for governor/engine/procedures + simulated long-running e2e).
- Wiki/Goals alignment note or new Autonomy operating page (if wiki-sync enabled).

## Open Questions (to be refined in child Research/Design stubs)

- Precise cost estimation model (Research child 1).
- Whether "Maintenance" becomes a first-class issue type or reuses Audit/Task + special labels.
- Webhook-driven vs poll for the absolute lowest latency (future, after core engine lands).
- Extension contribution model for custom procedures (can they register new tool allow-list entries?).
- How autopilot_score is exactly computed and whether it appears in GitHub Project fields.
- Interaction with multi-track release branches and autonomous release-readiness (may be a stretch child).

## Acceptance Evidence

- User can `gh plate config edit` (or hand-edit), set `autonomy.risk_tolerance: "high"`, `token_budget.daily: 30000`, enable schedules; commit.
- With a host scheduler invoking `gh plate autonomy run --loop --max-cycles 20` (or overnight), the engine performs multiple cycles: runs due procedures whose risk allows, respects daily budget (throttles or pauses before overspend), produces only terse terminal output per quiet rules, creates auditable PLATE-* markers and (where appropriate) child stubs or PR progress.
- `plate_autonomy_status` and health show live budget remaining, autopilot_score >0, recent procedure runs, and any human checkpoints surfaced.
- A risk:medium PR opened by an allowed agent is auto-merged (via generalized babysit + auto-merge) when `.plate` `autonomy.risk_tolerance` permits (and guards pass); a risk:critical PR is never auto-merged.
- All changes land via normal PLATE atomic PRs with fragments; the Epic itself follows the full planning → stub children → implementation loops.
- Dogfooding: this very Epic's planning session produced the design doc + GitHub Epic + child stubs; subsequent implementation slices for this Epic are executed (where safe) under the emerging autonomy settings.
- Existing repos using only the legacy `.github/AUTONOMOUS_MODE` file receive migration guidance via health/config surfaces and continue limited legacy behavior for a transition period; the recommended path is adding the `.plate` autonomy section (new repos and updated templates will not include the marker file). Full sunsetting of the file (removal from template payload inventory, workflows, AGENTS.md, features detection, etc.) is in scope for this Epic's children.

**Proving tests** (per test-classification convention): unit coverage of governor, procedure dispatch, risk filtering, budget pause paths; e2e that exercises a simulated multi-cycle run under budget constraint without human input; health + status surface tests.

This design directly realizes the interactive planning consensus: full governor in core, new AutonomyEngine class + MCP/CLI, data-driven procedures under `.agentic/procedures/`, adopted risk matrix, prioritized love features (budget visibility, single risk knob, recurring magic, autopilot score), and the full interactive planning + creation flow used to birth the Epic.

---

**Planning provenance:** Interactive Q&A (two rounds) via Grok Build TUI on the plate repository. Consensus captured: title, risk model, full governor, AutonomyEngine shape + surfaces, procedures schema + built-ins, child list, "create Epic + stubs in session" flow, dogfood fragments. All per PLATE AGENTS.md (Design artifact here, GitHub Epic as traceable issue artifact, fragments for process change, human judgment preserved).

## Usage Note (for this planning session)

This design + the subsequent GitHub Epic/child creation constitute the traceable artifact for the planning work. No Feature or Question was closed in this session, so no USAGE REPORT block is required on an issue closure; the design doc and Epic body serve as the record. Future implementation children will carry proper usage blocks on their closures.

## Implementation Status (after autonomous slices for #473/#474/#478/#482)
- Data models realized exactly as specified: `AutonomyStatus`, `ProjectSnapshot`, `CycleReport`, `ProcedureDef` (see `src/plate_core/autonomy.py`).
- Engine methods: `get_status`, `introspect` (health+epics+costs+config), `enforce_budget` (daily UTC reset, per-cycle/daily caps, throttle/pause/warn actions), `decide_next` (what_next + risk-filtered due procedures from snapshot), `run_cycle` (dry_run support, markers), `run_procedure`, `tick_schedules` (cadence + risk gate), `_load_procedures` ( .agentic/procedures/*.json + builtins for drift/feedback/cost).
- Risk handling: `_risk_rank` helper; comparisons now consistent (str levels ranked to int before <=); high tolerance allows more, critical never auto.
- Observability: autopilot_score computation (risk + budget burn + proc count); integrated in status/health.
- Quiet + safety: respects quiet ops for loops; budget before any action; human checkpoints (need:human-review, AGENTS/SPEC changes, critical) always preserved.
- Tests: units for load/risk/budget/status/cycle + e2e dry-run stub (see PR #493).
- Procedures: data-driven + 3+ builtins; risk gated.
This fulfills the Design child AC ("polished contract doc ... plus data models that can be implemented").

