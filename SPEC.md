---
spec_version: "2.0"
process_version: "PLATE 1.0 (target)"
owner: "akasper"
updated_at: "2026-05-29"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is **human-owned and agent-assisted**. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change.

## Purpose of PLATE

**PLATE** (Project Lifecycle Agentic Task Ecosystem) is the operating system for reliable, high-velocity agentic software development on GitHub. It empowers AI agents to own as much of the end-to-end software development lifecycle (SDLC) as possible — planning, implementation, testing, documentation, triage, and deployment — while enforcing **test-first discipline** (TDD/BDD), continuous verifiable progress, atomic PRs, and human judgment on architecture, risk, and releases.

GitHub is the default single source of truth: Issues for planning, Projects/Milestones for tracking, Workflows for gates, Copilot agents + MCP for execution, Pages/Wiki for docs/marketing. PLATE makes this ecosystem inspectable, actionable, and autonomously operable via shared runtime surfaces (`gh plate`, `plate-mcp`, Copilot CLI plugin).

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
- High agent autonomy with safety gates, risk-based auto-merge, and human judgment preserved.
- Observability: health, velocity, cost, drift detection, and dashboards.
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
  - `AGENTS.md` (authority, rules, autonomy levels)
  - `.plate/config.yml` (machine-readable settings: autonomy level, test prefs, etc.)
- **Progressive features**: Playwright E2E, autonomous mode, skill marketplace, visualization dashboards, multi-agent orchestration, simulation mode.

---

## Target Workflows

- `gh plate bootstrap --apply` → fully scaffolded PLATE repo.
- `/agent plate "Implement feature X"` → agent plans, implements test-first, opens atomic PR.
- `gh plate health` + `gh plate epic status` → instant confidence before review/merge.
- Agents self-correct low-risk issues; escalate via Issues for human judgment.

---

## Constraints

- GitHub API only (REST + GraphQL); stateless beyond minimal config.
- Zero runtime dependencies for binaries.
- Rate-limit aware and secret-safe.
- PLATE label taxonomy assumed (degraded gracefully otherwise).

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

## Ideas / Moonshots

- `.plate` marketplace for certified skills and agents.
- PLATE Simulator (safe fork + dry-run cycles).
- Cross-project intelligence (privacy-preserving).
- Self-hosting PLATE (a PLATE repo that manages other PLATE repos).
- Business outcome tracking linked to features.
- Voice/multimodal agent interfaces.

---

**Agent Instruction**: Always align work against this SPEC.md. Proactively update `CURRENT.md` to reflect reality. This document serves as the guiding vision. Use it ruthlessly to drive decisions.