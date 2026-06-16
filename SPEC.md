---
spec_version: "2.0"
process_version: "PLATE 1.0 (target)"
owner: "akasper"
updated_at: "2026-06-13"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is **human-owned and agent-assisted**. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change.

## Purpose of PLATE

**PLATE** (Project Lifecycle Agentic Task Ecosystem) is the operating system for reliable, high-velocity agentic software development on GitHub. It empowers AI agents to own as much of the end-to-end software development lifecycle (SDLC) as possible — planning, implementation, testing, documentation, triage, and deployment — while enforcing **test-first discipline** (TDD/BDD), continuous verifiable progress, atomic PRs, and human judgment on architecture, risk, and releases.

GitHub is the default single source of truth: Issues for planning, Milestones for Epic tracking, Projects for roadmap visualization, Workflows for gates, Copilot agents + MCP for execution, Pages/Wiki for docs/marketing. PLATE makes this ecosystem inspectable, actionable, and autonomously operable via shared runtime surfaces (`gh plate`, `plate-mcp`, Copilot CLI plugin).

**North Star**: Any repository (new or existing) can adopt PLATE in <15 minutes and achieve **70-90% agent-driven SDLC** with minimal human toil, while remaining lightweight, GitHub-native, and evolvable. Success metric: Widespread adoption as the de facto standard for agentic teams.

---

## Vision

`plate_core` is a single-binary (or lightweight), multi-surface library that makes PLATE project state inspectable, actionable, and agent-accessible from any interface. It is the runtime layer that connects human developers and AI agents to the live health, structure, operating rules, and autonomous capabilities of any PLATE repository.

The project ships in three primary forms from one codebase:

| Surface              | Install command                          | Target user                  | Invocation style                          |
|----------------------|------------------------------------------|------------------------------|-------------------------------------------|
| `gh plate` extension | `gh extension install akasper/plate`    | Human developers & scripts   | Terminal commands (`gh plate health`)     |
| `plate-mcp` server   | Binary or `npx plate-mcp`                | AI agents                    | Structured tool calls via `/mcp`          |
| Copilot CLI plugin   | `copilot plugin install akasper/plate`   | Conversational users         | Agent chat (`/agent plate`)               |

**plate_core** provides shared logic (health engine, epic/feature queries, bootstrap, baseline catalog, agent guidance). The plugin surface bundles `plate.agent.md` (proactive context gathering) and `.mcp.json` wiring. Future surfaces (VS Code, Raycast, CI actions) are additive.

PLATE follows a **Ruby on Rails** philosophy: strong conventions (labels, workflows, AGENTS.md, SPEC/CURRENT separation, test-first) with progressive enhancement and extensibility. It is designed for deep GitHub/Microsoft integration while planning for future adapters to other platforms.

---

## Users and Personas

| Persona                        | Need                                                      | Success Signal |
|--------------------------------|-----------------------------------------------------------|---------------|
| PLATE project developer (human)| Quickly check health, epic status, and next actions      | `gh plate health` in <2s with clear pass/warn/fail |
| AI agent (Copilot, etc.)       | Structured, typed access to project state                 | Reliable MCP tool calls driving autonomous work |
| Interactive Copilot CLI user   | Conversational assistant that proactively surfaces state  | Agent asks smart questions and delivers actionable plans |
| PLATE platform maintainer      | Single codebase for all surfaces                          | Changes flow seamlessly to gh, MCP, and plugin |
| PLATE new-project operator     | Frictionless bootstrap                                    | New repo fully scaffolded in minutes |
| Solo indie hacker / founder    | Fast autonomous velocity                                  | Zero-to-production features in days |
| Agentic engineering team lead  | Minimal review burden                                     | >70% agent-authored & auto-merged PRs |
| Enterprise platform team       | Compliance, auditability, scale                           | Centralized health + policy enforcement |

---

## Goals

- Single library powering multiple surfaces with zero behavioral drift.
- Instant project health visibility and structured state for agents.
- Near-zero-friction bootstrap and adoption.
- **Test-first mandatory** + continuous verifiable progress (SPEC → CURRENT).
- **High agent autonomy with safety gates, risk-based auto-merge, and human judgment preserved.** Autonomy is the default PLATE philosophy (always-on unless explicitly "off" via .plate); a single `risk_tolerance` knob (off/low/medium/high) plus token budgets and scheduled procedures govern long-running operation at the user's budgeted rate. Core runtime is the AutonomyEngine (introspects health/epics/costs/config/procedures, enforces budgets via Decision (PROCEED/THROTTLE/PAUSE/WARN), decides next actions, executes or delegates via plate_delegate_to_agent, with full observability: autopilot_score, burn_rate, due procedures, human checkpoints). Surfaces: plate_autonomy_status / run_cycle / run_procedure / list_procedures (MCP) and `gh plate autonomy status|run|loop`. .plate is the single source of truth for the autonomy section (replaces legacy .github/AUTONOMOUS_MODE marker during transition). Procedures are data-driven in .agentic/procedures/ (cadence, risk_level, allow-listed steps). Babysit + auto-merge generalized to consult .plate risk_tolerance. See Epic #470 and children (#471 research on budget governor models, #472 design contract, #473 .plate schema, #474 engine skeleton + Decision/estimate_cost, #475 CLI, #476 generalize auto-merge/babysit, #477 full plate_plan_epic with risk-aware stubs, #478 procedures registry, #479 observability, #480 persona/quiet updates, #481 docs/AGENTS, #482 tests).
- Observability: health, velocity, cost (harvested USAGE REPORTs), drift detection, autopilot_score / burn_rate in autonomy status + health, and dashboards.
- Acquisition readiness: clean architecture, strong GitHub integration, measurable Copilot impact.
- Extensibility: future multi-host adapters while staying GitHub-first.

---

## Non-Goals

- Storing project state outside GitHub (stateless core).
- Building a full project management UI.
- Replacing GitHub CLI or core GitHub functionality.
- Supporting non-test-first workflows.
- Vendor neutrality at the expense of deep GitHub integration (extensibility is progressive).

---

## Architecture & Core Components

- **Recommended stack**: TypeScript (preferred for SDKs and Copilot alignment) or Go (single binaries). Python acceptable only for rapid validation.
- **Core files** (enforced via bootstrap/health):
  - `SPEC.md` (intent)
  - `CURRENT.md` (verified reality)
  - `AGENTS.md` (authority, rules, autonomy levels, quiet operations)
  - `.plate` (machine-readable root config: versioned schema with autonomy section (risk_tolerance, token_budget {daily,per_cycle,action}, cost_ceiling_usd, schedules_enabled, loop), plus methodology/release/extensions; single source for autonomy replacing legacy AUTONOMOUS_MODE marker)
- **Progressive features**: Playwright E2E, autonomous mode, skill marketplace, visualization dashboards, multi-agent orchestration, simulation mode.

---

## Target Workflows

- `gh plate bootstrap --apply` → fully scaffolded PLATE repo.
- `/agent plate "Implement feature X"` → agent plans, implements test-first, opens atomic PR.
- `gh plate health` + `gh plate epic status` → instant confidence before review/merge.
- Agents self-correct low-risk issues; escalate via Issues for human judgment. Long-running autonomous operation via `gh plate autonomy run --loop` (or host scheduler) at budgeted token rate, with risk-gated procedures (drift, info audit, feedback integration/babysit, cost rollup, etc.) and full markers + USAGE REPORTs.

---

## Constraints

- GitHub API only (REST + GraphQL); stateless beyond minimal config.
- Zero runtime dependencies for binaries.
- Rate-limit aware and secret-safe.
- GitHub Milestones for Epic tracking; PLATE label taxonomy assumed (degraded gracefully otherwise).

---

## Success Metrics

- 100+ public PLATE repositories.
- Agent PR ratio >70% in mature projects.
- Bootstrap time <15 minutes.
- Strong acquisition interest from Microsoft/GitHub.

---

## Risks & Mitigation

- Vendor lock-in → Progressive extensibility layer.
- Human bottlenecks → Health-driven autonomy + clear escalation.
- Adoption friction → Obsessive bootstrap and documentation focus.
- Execution velocity → Relentless dogfooding + atomic PRs.

---

## Beta Roadmap — Epics for Feature Completeness

The following prioritized epics and work items were identified from analysis of the current repository state (post-v0.1.4 releases + unreleased fragments in `.agentic/releases/unreleased/`, active Epic #218 Information Audit and children, design artifacts under `docs/design/`, research notes under `docs/research/`, code-level stubs and v1 implementations, test coverage, bootstrap/health/feature surfaces, and strict alignment to the North Star, Goals, and target workflows above).

Completing these (in approximate priority order, sequenced to minimize merge conflicts and build on landed Curiosity/Q&A, CLI-agnostic plugin, babysit, and Audit work) is the expected path to **feature completeness for a beta release**: frictionless <15-minute adoption for new and existing projects, robust 70-90% agent-driven SDLC, strong safety gates (test-first, atomic PRs, human judgment on risk/architecture/release), and full inspectability/actionability across the three surfaces (`gh plate`, `plate-mcp`, CLI agent plugin).

Each item should be opened as its own Epic (or Feature) issue, linked to the appropriate milestone, and executed per the Required Work Loop in AGENTS.md (labeling, tests alongside implementation, per-feature fragments, atomic PRs with clean titles and `Closes #N`, etc.). Many directly close visible gaps such as documented stubs and "minimal" slices.

- **Epic: Autonomous PLATE Engine & Scheduled Procedures (#470)**  
  The heart of the PLATE vision: first-class AutonomyEngine runtime (plate_core/autonomy.py) that introspects project state (health + epics + costs + config + due procedures), enforces token budgets via Decision + #471 heuristics (over-estimate, historical from costs/.agentic/COSTS.md, scope multipliers), decides next (risk-filtered procedures + what_next), executes or delegates, logs PLATE-AUTONOMY-CYCLE markers + USAGE REPORTs, and exposes observability (autopilot_score, burn_rate). .plate autonomy section (risk_tolerance off/low/medium/high, token_budget, cost_ceiling_usd, schedules_enabled, loop) is the single source (sunsets .github/AUTONOMOUS_MODE). Data-driven procedures in .agentic/procedures/ (nightly-drift-detection, feedback-integration, cost-rollup, etc.). MCP surfaces (plate_autonomy_*) + `gh plate autonomy status|run|loop`. Generalize babysit/auto-merge to .plate risk_tolerance. Full plate_plan_epic with risk-aware auto-stub generation at high tolerance. Persona/AGENTS/quiet updates. Tests + design/research artifacts. (Children #471–482 landed or in flight; see design doc and fragments.)

- **Epic: Full Interactive Epic Planning Engine (plate_plan_epic + gh plate plan / MCP surfaces)**  
  Replace the Phase-1 stub implementation (`_plan_epic_stub` returning only schema + "host agent's chat or gh plate qanda" note in `src/plate_core/mcp_server.py:34`) with a full guided interactive planning flow. The tool/MCP/CLI surface should create the parent Epic issue + `Epic: short-name` label + ordered child stubs (Research → Design → Feature, auto-labeled `need:refinement`), seed PLATE_SESSION_STATE JSON, integrate with Q&A / bootstrap seeding, and compose with Information Audit. Add a top-level `gh plate plan` (or `epic plan`) command. See sibling designs (interactive-planning-ux.md, epic-intent-detection.md, qanda-mcp-cli-surfaces.md, single-agent-delegation-flow.md) and the planning sections in the template `AGENTS.md`. (Risk-aware auto-stub generation added in #477 as part of #470.)

- **Epic: Contemplation Engine v2 + Full Contract + Reliable Close Logic**  
  Evolve the current heuristic/minimal ContemplationEngine (`src/plate_core/contemplation.py`, invoked via `plate_contemplate` / RecordAnswerTool / MCP) to the complete, enforceable contract defined in Design #143. Must include: full transcript append (non-destructive), deterministic parsing of `answer_signal` from Question bodies, creation of forward-progress artifacts (new linked issues of appropriate types + direct mutations to AGENTS.md / `.agentic/releases/` fragments / SPEC.md / wiki sources / docs/ per the relevant rules), append-only revision handling with `revision_of`, unblock/resume merge for answers to blocking Questions (#147 creation + #148 resumption), and Question closure *if and only if* the answer_signal criteria are verifiably met (citing excerpts; always include the `=== USAGE REPORT ===` block on close). Update agent_guidance.py, `plugin/agents/plate.agent.md`, and baseline catalog entries. This is the core behavioral engine that turns Curiosity answers into durable progress while preserving the four invariants from Epic #139.

- **Epic: Curiosity Answer Model — Committed Storage, Indexing, and Query**  
  Implement the secondary committed artifact layer from Design #142 (Answer Model & Provenance Strategy) on top of the primary structured GitHub issue comment blocks (`<!-- plate-answer-provenance ... -->` + `<!-- PLATE-ANSWER:BEGIN -->`). Add `docs/curiosity/answers/<kebab-slug>.md` (append-only logs) and a central index (`docs/curiosity/answers-index.json` or equivalent). Enhance `plate_get_answers` (and add richer query tools), provide fast local/agent lookup for cloned repos, and include a one-time backfill/migration command for historical Questions. GitHub comments (and GraphQL search) remain the durable source of truth; committed form is for performance and discoverability. Ties directly to `GetAnswersTool`, contemplation, and the research inventory in curiosity-qanda-inventory.md. Enables reliable synthesis when a project accumulates many open Questions.

- **Epic: .plate Root Config Lifecycle — CLI/MCP Surfaces + Extension Support + Health Integration**  
  Complete the MVP parser/validator/resolver in `src/plate_core/plate_config.py` (and `test_epic89_plate_config.py`) with first-class surfaces: `gh plate config` subcommands (init / configure / validate / upgrade), corresponding MCP tools (`plate_config_*`), deep merge for extensions (tool defaults < enabled extensions < local overrides per the precedence in the design), schema evolution helpers, and `save`. Wire the results into health checks, bootstrap (`--apply` seeding), features detection, and CI-facing validation. See the full design in `docs/design/plate-root-config-schema-lifecycle.md` and the owning Epic #89 / Issue #108 / #129 work. This is the explicit, machine-readable boundary between tool-owned methodology and repo-owned policy/customization.

- **Feature: Implement local-rebase Branch-Update Strategy in PR Babysit**  
  Deliver the `local-rebase` option for `--branch-update-strategy` (currently documented in AGENTS.md §Base Branch Sync Handling and the babysit research doc as "not yet implemented" and raising NotImplementedError). Provide safe local worktree rebase + push logic, conflict/ dirty-state handling, comprehensive tests (extending `tests/test_pr_babysit.py`), CLI/MCP parity, and clear escalation paths (e.g. `need:human-review` for complex cases). The default "copilot-request" (and "none") strategies remain; this completes the matrix. Part of making the babysit loop (v0.1.4 base-sync work + #197) fully autonomous where safe.

- **Epic: First-Class Release Tooling (gh plate release cut + Ceremony Automation)**  
  Promote the existing `scripts/cut_release.py` (plus `render_release_notes.py` / `render_release_migrations.py`) into native core surfaces: `gh plate release cut <version>` (and MCP `plate_release_cut`), with auto-version inference from prior releases + fragments + tags (building on recent #253 auto-detect work), collection from both `unreleased/` and `epic-*/` directories, emission of the versioned `.agentic/releases/vX.Y.Z/` layout + `release.json`, and support for the full release ceremony steps (including post-merge tag + hard-reset of the release branch). Enhance `release status` with more ceremony readiness signals. Aligns with the three-tier branch model, bootstrap's release-branch action, and the detailed Release ceremony in AGENTS.md. Removes reliance on external scripts for the canonical flow.

- **Epic: Expanded Health/Features/Doctor + Convention Enforcement**  
  Extend `get_health` (health.py) and `get_features` (features.py) — and their CLI/MCP surfaces — with additional high-value signals: presence and validity of `.plate` / config, adoption of the Goals wiki page (from #218), open Question count + Curiosity/Q&A activity, release-branch existence + protection status, Playwright evidence quality, binary hygiene improvements, etc. Introduce a `gh plate doctor` (or `gh plate health --fix` / MCP equivalent) that can safely apply low-risk remediations (labels, seed Questions, fragment layout nudges) while escalating others. Add light convention enforcement and helpful diagnostics in bootstrap output. Makes "instant project health visibility" (SPEC) and progressive enhancement more actionable for both humans and agents.

- **Epic: Playwright E2E + Visual Evidence Polish and Integration**  
  Harden and extend the existing E2E tooling (`src/plate_core/mcp/tools.py` + `InitPlaywrightTool` etc., local detection in features.py, and the full scaffolding in `src/plate_core/template_payload/tests/e2e/`). Improvements: higher-quality / trimmed / multi-format GIF recording in `record_e2e_gif`, stricter validation rules (missing specs, CI integration, evidence in PRs), better error messages, and explicit hooks into Feature PR expectations, the documentation gate, agent guidance (`plugin/agents/plate.agent.md`), and the `gh plate features` output. Builds on the #64 heuristic and visual-evidence tracking. Turns the "Playwright E2E Testing" optional capability into a first-class, low-friction recommendation for UI-facing projects.

- **Epic: Baseline Catalog Expansion + Extensibility Foundations**  
  Grow the catalog (`src/plate_core/data/baseline_catalog.yml` and `baseline_catalog.py`) with additional agents and skills that provide fuller SDLC coverage (e.g. security auditor, performance/reliability engineer, data/privacy roles, advanced devops/release variants) while preserving the tight constraint and example discipline. Advance the extension packaging + contribution model for skills/agents/default informational goals/audit behaviors (see `docs/research/plugin-foundation-packaging-and-security.md`, `docs/design/mcp-agent-skill-tool-surface.md`, `docs/research/plate-extension-model-evolution.md`, and the extension goals work in #222/#226). Keep `plate_agents` / `plate_skills` / `plate_delegate_to_agent` / guidance surfaces fully consistent. Strengthens the "Baseline Agents Catalog" feature and delegation story.

- **Epic: Observability, Cost Aggregation, and Velocity Surfaces**  
  Add dedicated MCP tools and `gh plate` subcommands (e.g. `plate_costs`, `plate_usage`, `plate_velocity` or `gh plate metrics`) that harvest the required `=== USAGE REPORT ===` blocks (mandated on Question/Feature/Epic close per AGENTS.md), compute aggregated token/cost/velocity numbers per Epic, release, or time window (with explicit assumptions), and emit machine-readable + wiki-updatable artifacts. Deep integration with the existing "accountant" baseline agent and release notes pipeline. Directly realizes the SPEC "Observability: health, velocity, cost, drift detection, and dashboards" goal and the "measurable Copilot impact" success metric. Also supports cost-related moonshots.

**Supporting / cross-cutting items** (suitable as Features inside the Epics above or small standalone work):
- Wiki sync defaults, reliability, and Goals page bootstrap/enforcement (directly extends #218 / #224 / #229).
- Packaging, distribution, and install UX hardening for beta (PyPI package for plate_core, improved `plate-mcp` binary, gh extension polish, version alignment across surfaces; note that current Python implementation was for rapid validation per SPEC stack guidance and `docs/research/stack-selection.md`).
- Deeper GitHub Projects v2 field integration and milestone enforcement signals in health/epic surfaces.
- Expanded multi-host verification harness + certification (beyond current `tests/e2e/` copilot-plugin + plugin-structure specs) to back CLI-agnostic claims.
- Error resilience, rate-limit handling, partial-failure recovery, and secret-safety hardening across github_client.py and all tool paths.

Completion of the active Information Audit Epic #218 plus the items above (plus any human refinements) should position PLATE for a confident beta. Future updates to this section should be made via Documentation PRs that also add/update fragments.

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