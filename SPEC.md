---
spec_version: "2.1"
process_version: "PLATE 1.0 (target)"
owner: "akasper"
updated_at: "2026-07-26"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is **human-owned and agent-assisted**. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change. Intent changes that affect autonomy, release ceremony, or agent surfaces ship via Documentation PRs with fragments under `.agentic/releases/unreleased/`.

## Purpose of PLATE

**PLATE** (Project Lifecycle Agentic Task Ecosystem) is the operating system for reliable, high-velocity agentic software development on GitHub. It empowers AI agents to own as much of the end-to-end software development lifecycle (SDLC) as possible — planning, implementation, testing, documentation, triage, and deployment — while enforcing **test-first discipline** (TDD/BDD), continuous verifiable progress, atomic PRs, and human judgment on architecture, risk, and releases.

GitHub is the default single source of truth: Issues for planning, Milestones for Epic tracking, Projects for roadmap visualization, Workflows for gates, Copilot agents + MCP for execution, Pages/Wiki for docs/marketing. PLATE makes this ecosystem inspectable, actionable, and autonomously operable via shared runtime surfaces (`gh plate`, `plate-mcp`, Copilot CLI plugin).

**North Star**: Any repository (new or existing) can adopt PLATE in <15 minutes and achieve **70-90% agent-driven SDLC** with minimal human toil, while remaining lightweight, GitHub-native, and evolvable. At maturity, a repo runs **long-running autonomous cycles at the user's budgeted token/cost rate** (AutonomyEngine + scheduled procedures + quiet agent loops), with human judgment only at defined checkpoints. Success metric: Widespread adoption as the de facto standard for agentic teams.

---

## Vision

`plate_core` is a single-binary (or lightweight), multi-surface library that makes PLATE project state inspectable, actionable, and agent-accessible from any interface. It is the runtime layer that connects human developers and AI agents to the live health, structure, operating rules, and autonomous capabilities of any PLATE repository.

At the center of that runtime is the **AutonomyEngine** (Epic #470): software that introspects project state (health, epics, costs, `.plate` config, due procedures), enforces budgets, decides the next safe action, and executes or delegates — so autonomy is engine-driven, not only persona prose + host loop scripts. Humans keep judgment; agents and the engine do the toil.

The project ships in three primary forms from one codebase:

| Surface              | Install command                          | Target user                  | Invocation style                          |
|----------------------|------------------------------------------|------------------------------|-------------------------------------------|
| `gh plate` extension | `gh extension install akasper/gh-plate`    | Human developers & scripts   | Terminal commands (`gh plate health`, `gh plate autonomy`) |
| `plate-mcp` server   | Binary or `npx plate-mcp`                | AI agents                    | Structured MCP tool calls (`plate-mcp`)   |
| Copilot CLI plugin   | `copilot plugin install akasper/plate`   | Conversational users         | Agent chat (`/agent plate`)               |

**plate_core** provides shared logic (health engine, AutonomyEngine, epic/feature queries, bootstrap, baseline catalog, agent guidance, feed/planning/PM surfaces, SPEC audit). The plugin surface bundles `plate.agent.md` (proactive context gathering, default plate persona) and `plugin/.mcp.json` wiring. Future surfaces (VS Code, Raycast, CI actions) are additive.

PLATE follows a **Ruby on Rails** philosophy: strong conventions (labels, workflows, AGENTS.md, SPEC/CURRENT separation, test-first) with progressive enhancement and extensibility. It is designed for deep GitHub/Microsoft integration while planning for future adapters to other platforms.

---

## Users and Personas

| Persona                        | Need                                                      | Success Signal |
|--------------------------------|-----------------------------------------------------------|---------------|
| PLATE project developer (human)| Quickly check health, epic status, and next actions      | `gh plate health` in <2s with clear pass/warn/fail |
| AI agent (Copilot, etc.)       | Structured, typed access to project state                 | Reliable MCP tool calls driving autonomous work |
| Interactive Copilot CLI user   | Conversational assistant that proactively surfaces state  | Agent asks smart questions and delivers actionable plans |
| Autonomy / budget operator     | Configure risk, token budgets, schedules; trust unattended runs | `gh plate autonomy --status` shows risk, burn, remaining budget, due procedures; no surprise spend |
| PLATE platform maintainer      | Single codebase for all surfaces                          | Changes flow seamlessly to gh, MCP, and plugin |
| PLATE new-project operator     | Frictionless bootstrap                                    | New repo fully scaffolded in minutes |
| Solo indie hacker / founder    | Fast autonomous velocity                                  | Zero-to-production features in days |
| Agentic engineering team lead  | Minimal review burden                                     | >70% agent-authored & auto-merged PRs (within risk_tolerance) |
| Enterprise platform team       | Compliance, auditability, scale                           | Centralized health + policy + decision ledger |

---

## Goals

- Single library powering multiple surfaces with zero behavioral drift.
- Instant project health visibility and structured state for agents.
- Near-zero-friction bootstrap and adoption.
- **Test-first mandatory** + continuous verifiable progress (SPEC → CURRENT).
- **High agent autonomy with safety gates, risk-based auto-merge, and human judgment preserved.** Autonomy is the default PLATE philosophy (always-on unless explicitly `risk_tolerance: "off"` in `.plate`). A single `risk_tolerance` knob (`off` / `low` / `medium` / `high`) plus token budgets and scheduled procedures govern long-running operation at the user's budgeted rate.
  - **Core runtime:** `AutonomyEngine` in `plate_core` introspects health/epics/costs/config/procedures; enforces budgets via `Decision` (`PROCEED` / `THROTTLE` / `PAUSE` / `WARN`); decides next actions; executes or delegates; records markers (`PLATE-AUTONOMY-CYCLE`, `PLATE-PROCEDURE-RUN`) and USAGE REPORTs; exposes observability (`autopilot_score`, `burn_rate`, due procedures, open human checkpoints).
  - **Config single source:** `.plate` `autonomy` section (risk_tolerance, token_budget, cost_ceiling_usd, schedules_enabled, loop, pr_review_scope). Replaces legacy `.github/AUTONOMOUS_MODE` marker (supported only for transition/migration guidance).
  - **Procedures:** data-driven definitions under `.agentic/procedures/` (cadence, risk_level, allow-listed steps).
  - **Surfaces:** MCP `plate_autonomy_status` / `run_cycle` / `run_procedure` / `list_procedures` / `simulate`; CLI `gh plate autonomy status|run|loop|--simulate|--dashboard`.
  - **Safety stack (v1.0 path):** shadow/simulation for high-impact actions (#645), unified checkpoint/approval primitive (#648), provenance/decision ledger (#647), cost+risk dashboard (#653/#634). Engine pauses on open checkpoints; high/critical actions require shadow_ack + approval when gates apply.
  - **Coordination:** Q+Task feed (#631), Q&A planning surfaces (#628/#630/#629/#640), Project Manager orchestrator (#660) assign work above AutonomyEngine without replacing it. Architecture/personas/API sketch: `docs/design/pm-orchestrator-architecture-and-browser.md` (#662). Browser surface (#661) is future; TUI feed is current.
  - See Epic #470 + children #471–482, design `docs/design/autonomous-plate-engine.md`, and AGENTS.md §Autonomous Mode + Project Manager guidance.
- Observability: health, velocity, cost (harvested USAGE REPORTs), drift detection, autopilot_score / burn_rate, cost+risk dashboard feed items, and decision ledger queries.
- Acquisition readiness: clean architecture, strong GitHub integration, measurable Copilot impact.
- Extensibility: future multi-host adapters while staying GitHub-first.

---

## Non-Goals

- Storing project state outside GitHub (stateless core; durable ledgers under `.agentic/` are repo-local artifacts, not a separate SaaS state store).
- Building a full project management UI (browser/rich UI is deferred; CLI/MCP first).
- Replacing GitHub CLI or core GitHub functionality.
- Supporting non-test-first workflows.
- Vendor neutrality at the expense of deep GitHub integration (extensibility is progressive).
- Unbounded unattended spend or self-escalating risk (engine must not raise `risk_tolerance` or bypass budgets).

---

## Architecture & Core Components

- **Recommended stack**: TypeScript (preferred for SDKs and Copilot alignment) or Go (single binaries). Python is the current rapid-validation implementation (see `docs/research/stack-selection.md`); distribution targets remain multi-surface from one codebase.
- **Core files** (enforced via bootstrap/health):
  - `SPEC.md` (intent)
  - `CURRENT.md` (verified reality)
  - `AGENTS.md` (authority, rules, autonomy levels, quiet operations)
  - `.plate` (JSON root config: versioned schema with `autonomy` section — `enabled`, `risk_tolerance`, `token_budget` {daily, per_cycle, action}, `cost_ceiling_usd`, `schedules_enabled`, `loop`, `pr_review_scope` — plus methodology/release/extensions; **single source** for autonomy, replacing legacy `AUTONOMOUS_MODE` marker)
- **AutonomyEngine runtime** (`src/plate_core/autonomy.py` and related modules):
  - Introspect → enforce_budget → decide_next → execute/delegate cycle
  - Procedures registry (`.agentic/procedures/`) + built-ins (drift, feedback integration, cost rollup, …)
  - Safety: shadow/simulate gates, checkpoints (`.agentic/checkpoints/`), decision ledger (`.agentic/ledger/`)
  - PM orchestrator (`pm.py`) coordinates persona team assignments above the engine
  - Feature/bug loops (`feature_loop.py`, `bug_loop.py`) hydrate live #634 remaining and charge durable spend on start even when `risk_tolerance=off`
  - Fleet handoffs (`fleet.py`): accept dispatches implementer→feature/bug loop, researcher/design→#632 artifact, reviewer→babysit; high-risk handoffs open checkpoints
- **SPEC audit** (`spec_audit.py`): structured findings (aligned/undocumented/stale_evidence); `gh plate spec-audit --followups` / MCP `plate_spec_audit_followups` route to Documentation/Bug/Question with human gate on SPEC writes
- **Adoption import**: `import_payload.py` + `template_payload_manifest.yml` path_rules (safe|conservative|force, install_as, conflict strategies); `gh plate import-payload` / `plate_import_payload`
- **template_payload adopter harness**: `tests/test_template_payload.py` proves adopter claims (AGENTS/SPEC, e2e scaffold, core workflows present; `list_payload_files` + import dry-run plan them) so <30m onboarding evidence is bidirectional (#917/#364 residual)
- **Surfaces**: `gh plate *` and MCP `plate_*` stay parity for health, epic, release, autonomy, feed, planning, checkpoint, ledger, pm, fleet, import-payload, spec-audit.
- **Progressive features**: Playwright E2E, skill marketplace, visualization dashboards, multi-agent team runtime depth, hybrid/non-code workflows.

---

## Target Workflows

- `gh plate bootstrap --apply` → fully scaffolded PLATE repo (including standing release tracks / Next Release as applicable).
- `/agent plate "Implement feature X"` → agent plans, implements test-first, opens atomic PR to the correct release base (`gh plate release status` first).
- `gh plate health` + `gh plate epic status` + `gh plate what-next` / `plate_what_next` → instant confidence and next process step.
- **what_next priority ladder (proved):** budget_gate → open_pr → adoption/self-migrate → ready_issue → pm_tick / active PM → epic closeout or stub refine when the PM queue is **idle** (do not force PM dry-run solely because `open_epic_count > 0`). Live idle-vs-active PM ranking is covered by integration-style tests in `tests/test_what_next.py` (#905/#907 proving path).
- **Budgeted autonomy:** operator sets `.plate` `autonomy.risk_tolerance` + budgets; agent or scheduler runs `gh plate autonomy --status` then `run` / `--loop` (or MCP `plate_autonomy_run_cycle`). Risk `off` disables engine autopilot only — ordinary Feature/Bug/Doc implementation still proceeds under human review rules.
- **Safety path:** high-impact actions use `plate_autonomy_simulate` / shadow reports; open checkpoints pause cycles until decide/approve; ledger records decisions for audit.
- **Feed + planning:** `plate_feed` ranks open Questions/Tasks; Q&A planning builds Feature/Epic/Release stubs with approval prompts.
- **PR green loop:** `gh plate pr babysit N --act` (scope default `all`) with local-rebase or copilot-request for base sync; feedback-resolution gate for agent threads; human approval still required for Bug/Feature/Documentation merges unless autonomous eligibility is met.
- Agents self-correct low-risk issues; escalate via Issues / `need:human-review` for human judgment. Long-running runs stay quiet (terse bullets; GitHub comments only on real progress or exempt markers).

---

## Constraints

- GitHub API only (REST + GraphQL); stateless beyond minimal config and repo-local `.agentic/` artifacts (fragments, procedures, checkpoints, ledger, costs).
- Zero runtime dependencies for binaries (packaging goal).
- Rate-limit aware and secret-safe; no secrets in comments/commits.
- GitHub Milestones for Epic tracking; PLATE label taxonomy assumed (degraded gracefully otherwise).
- AutonomyEngine never self-escalates risk, weakens branch protection, or bypasses human Tasks (external accounts, credentials, marketplace publish).

---

## Success Metrics

- 100+ public PLATE repositories.
- Agent PR ratio >70% in mature projects.
- Bootstrap time <15 minutes.
- Unattended autonomous cycles sustainable for hours/days within configured token/$ budgets without silent overspend (governor + dashboard evidence).
- Operators can raise/lower touch via one `.plate` risk knob and see autopilot_score, burn_rate, and open checkpoints in status surfaces.
- Strong acquisition interest from Microsoft/GitHub.

---

## Risks & Mitigation

- Vendor lock-in → Progressive extensibility layer.
- Human bottlenecks → Health-driven autonomy + clear escalation + feed of Questions/Tasks.
- Adoption friction → Obsessive bootstrap and documentation focus.
- Execution velocity → Relentless dogfooding + atomic PRs.
- **Budget overrun / runaway loops** → Token/$ governor, Decision THROTTLE/PAUSE, cost dashboard (#653), quiet loop discipline.
- **Unsafe auto-merge / high-impact actions** → risk_tolerance matrix, eligibility guards, shadow/simulate (#645), checkpoints (#648), never auto-merge critical or high-risk paths (AGENTS.md, workflows, secrets).
- **Legacy AUTONOMOUS_MODE drift** → health/config migration guidance to `.plate` autonomy section; sunset marker as source of truth.
- **Intent drift (SPEC vs engine)** → this document + design/docs + fragments; Documentation PRs when vision shifts (this Issue #488 pattern).

---

## Beta / v1.0 Roadmap — Epics for Feature Completeness

The following prioritized epics and work items track the path from early beta through **v1.0.0 readiness** (Release #654: endless Q&A-driven autonomous product lifecycle). Sequencing minimizes merge conflicts and builds on landed Curiosity/Q&A, babysit, Audit, AutonomyEngine (#470), and release-ceremony work.

Completing these is the expected path to frictionless <15-minute adoption, robust 70-90% agent-driven SDLC, strong safety gates, and full inspectability/actionability across `gh plate`, `plate-mcp`, and the CLI agent plugin — with long-running budgeted autonomy as the default philosophy.

Each item should be opened as its own Epic (or Feature) issue, linked to the appropriate milestone, and executed per the Required Work Loop in AGENTS.md (labeling, tests alongside implementation, per-feature fragments, atomic PRs with clean titles and `Closes #N`, etc.).

### Landed core (Autonomy Engine — Epic #470)

- **Epic: Autonomous PLATE Engine & Scheduled Procedures (#470)** — **core delivered** (children #471–482 and related PRs). First-class AutonomyEngine (`plate_core/autonomy.py`): introspect → budget Decision → decide_next → execute/delegate; `.plate` autonomy section as single source (sunsets binary `AUTONOMOUS_MODE`); procedures in `.agentic/procedures/`; MCP `plate_autonomy_*` + `gh plate autonomy status|run|loop`; babysit/auto-merge generalized to risk_tolerance; risk-aware plan stubs; persona/quiet/AGENTS updates; observability (autopilot_score, burn_rate). Design: `docs/design/autonomous-plate-engine.md`. Remaining #470 polish is incremental; **do not re-sketch** landed gates as paper-only fragments.

### v1.0 safety + product path (Release #654)

Priority order for remaining work (agents: prefer finishing open PRs, then Phase 0 docs, then Phase 1 safety depth, then feed/planning, then PM):

1. **Phase 1 — Autonomy safety (harden real gates)**  
   - #645 simulation/shadow for high-impact actions (first surface landed; deepen enforcement E2E).  
   - #648 unified checkpoint/approval primitive (first surface landed; wire all high-impact paths).  
   - #634 / #653 budgets + cost/risk visibility in feed/dashboard.  
   - #647 provenance/decision ledger (engine writes ledger rows; query/summary surfaces).

2. **Phase 2 — Feed + Q&A planning (#656 cluster)**  
   - #631 Q+Task user feed → #628/#630 product/feature planning Q&A → #629/#640 release/epic planning → #632 design/research approval.

3. **Phase 3 — PM core (#660)**  
   - Long-running orchestrator (what_next → assign → budget → checkpoints). First slice landed (`plate_pm_*` / `gh plate pm`); deepen team runtime before browser UI (#661).

### Continuing beta completeness epics

- **Epic: Full Interactive Epic Planning Engine (plate_plan_epic + gh plate plan / MCP surfaces)**  
  Replace remaining stub paths with full guided interactive planning: parent Epic + ordered child stubs (Research → Design → Feature, `need:refinement`), session state, Q&A / bootstrap / Information Audit composition. Risk-aware auto-stub generation (#477) is part of the #470 stack. Sibling designs: interactive-planning-ux.md, epic-intent-detection.md, qanda-mcp-cli-surfaces.md.

- **Epic: Contemplation Engine v2 + Full Contract + Reliable Close Logic**  
  Evolve ContemplationEngine to the Design #143 contract: full transcript, deterministic `answer_signal`, forward-progress artifacts, revision_of, unblock/resume, close only when criteria met + USAGE REPORT. Core engine that turns Curiosity answers into durable progress (Epic #139 invariants).

- **Epic: Curiosity Answer Model — Committed Storage, Indexing, and Query**  
  Secondary committed layer (`docs/curiosity/answers/` + index) on top of GitHub comment provenance; richer `plate_get_answers` / query tools; backfill. GitHub remains source of truth.

- **Epic: .plate Root Config Lifecycle — CLI/MCP Surfaces + Extension Support + Health Integration**  
  Complete config surfaces (`gh plate config` init/configure/validate/upgrade + MCP), extension deep merge, schema evolution, health/bootstrap/CI wiring. Design: `docs/design/plate-root-config-schema-lifecycle.md` (Epic #89 / #108 / #129). Autonomy section is already first-class; lifecycle polish continues.

- **Feature: local-rebase Branch-Update Strategy in PR Babysit** — **delivered** (isolated worktree rebase + push; AGENTS.md + pr_babysit helpers; #514 isolation hardening). Default remains `copilot-request`; `none` for detect-only.

- **Epic: First-Class Release Tooling (gh plate release cut + Ceremony Automation)**  
  Native `gh plate release cut` / finalize, multi-track and legacy single-`release` modes, fragment aggregation, standing Next Release issue, heavy Release PR CI. Align with `docs/design/release-ceremony-refinement.md`.

- **Epic: Expanded Health/Features/Doctor + Convention Enforcement**  
  Richer health/features signals (`.plate` validity, Goals page, Questions, release protection, autonomy status). Doctor/low-risk remediations.

- **Epic: Playwright E2E + Visual Evidence Polish and Integration**  
  Harden E2E tooling, evidence in PRs, features detection, agent guidance hooks.

- **Epic: Baseline Catalog Expansion + Extensibility Foundations**  
  Grow agents/skills; extension packaging model; keep plate_agents / plate_skills / plate_delegate_to_agent consistent.

- **Epic: Observability, Cost Aggregation, and Velocity Surfaces**  
  `plate_costs` / dashboard / velocity from USAGE REPORTs; integrate with accountant agent and #653 cost+risk dashboard. Supports budgeted autonomy evidence.

**Supporting / cross-cutting items**:
- Wiki sync defaults and Goals page bootstrap (#218 / #224 / #229).
- Packaging/distribution (PyPI, gh extension, version alignment); human Tasks for trusted publisher / marketplace publish remain human-only.
- GitHub Projects v2 fields + milestone enforcement in health/epic surfaces.
- Multi-host verification harness; rate-limit and secret-safety hardening.

Completion of #470 core plus Phase 1–3 of #654 (with human refinements and production E2E proof — sketches ≠ done) positions PLATE for confident v1.0. Future updates to this section ship via Documentation PRs + fragments.

---

## Ideas / Moonshots

- `.plate` marketplace for certified skills and agents.
- PLATE Simulator (safe fork + dry-run cycles).
- Cross-project intelligence (privacy-preserving).
- Self-hosting PLATE (a PLATE repo that manages other PLATE repos).
- Business outcome tracking linked to features.
- Voice/multimodal agent interfaces.



**Update from velocity polish (fragments + Q&A #580/#569/#556):** Added minimal support for PLATE Issue states (status:implemented on release-branch merge before final to main; see #556, #582, workflow in pr-issue-link-check, label in labels.yml). Ceremony polish (Closes block, agent-only gate, CI stabilization, finalize enhancements) landed; see children #535/#583 etc and fragments. Update this section and epic guidance when new Epics created (per #537).

---

**Agent Instruction**: Always align work against this SPEC.md. Proactively update `CURRENT.md` to reflect reality. This document serves as the guiding vision. Use it ruthlessly to drive decisions.