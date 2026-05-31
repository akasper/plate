---
title: Design: Information Audit Contract, Behavior, and Platform Integration
issue: 223
epic: 218
status: draft
---

# Design: Information Audit Contract, Behavior, and Platform Integration

**Issue:** #223 (Design child of Epic #218 "Information Audit & Goal-Driven Question Generation")

**Designed by:** Grok (xAI)

**Date:** 2026-05-31

**Status:** Draft (for review and refinement)

## Design Goal

Define the precise, enforceable contract and runtime behavior for the **Information Audit** capability as a first-class, platform-level PLATE feature. This must work generically for *any* project adopting PLATE (via template, plugin, or MCP), enabling agents to proactively discover Informational Goals and generate high-quality `Question` issues.

The system builds on the Curiosity/Q&A machinery from Epic #139 but shifts from reactive (answering existing Questions) to proactive (discovering what Questions to ask, grounded in explicit project Goals).

## Key Concepts (recap from planning and #220)

- **Goal**: High-level documented intent/mission of the project (lives on the Wiki `Goals` page — see #219/#224 convention). Broad directional statements about why the project exists and how it will succeed (go-to-market, revenue, deployment, target outcomes, etc.).
- **Informational Goal**: A *concept* (not an artifact): "We need to know X so we can Y" in service of a Goal. Usually tied to at least one "Need to Know".
- **Question**: The GitHub Issue artifact that encapsulates an Informational Goal. Includes the goal statement, sample questions, provenance (where the gap was noticed), links to related artifacts that should be updated on resolution, and `answer_signal` for closure.

The audit bridges Goals → Informational Goals → Questions.

## Scope

- Core audit interface (MCP tools + CLI surface).
- Discovery behavior (how it reads the Wiki `Goals` page + other surfaces: code, issues, PRs, discussions, existing Questions, etc.).
- Question generation (structure, quality, provenance, traceability, continuous refinement).
- Platform integration (bootstrap, template, agent guidance, wiki sync, extensibility for extensions).
- Specialized scoping (e.g., marketing-focused vs. engineering-focused audits by agent type).
- Integration with existing systems (Curiosity/Q&A Mode, Contemplation Engine, Answer Model, blocking/resumption from #147/#148).
- Traceability and auditability requirements.

**Out of scope for this Design**: Exact UI/UX for surfacing audits (future TUI work), full classification taxonomy for Informational Goals (future), heavy machine-readable Goals page format (start flat per #219).

## Recommended Contract (MCP + CLI)

### Primary Tool: `plate_perform_information_audit`

**Inputs** (all optional except repo context):
- `repo`: owner/name (defaults to current).
- `scope`: "repo" | "epic:<number>" | "label:<name>" | "surface:wiki,issues,code" (default: repo-wide, open-ended).
- `agent_type`: e.g. "general", "marketing", "engineering", "research" (for specialized scoping/heuristics; default "general").
- `max_questions`: int (cap on new Questions to propose/create; default 5-10 for focus).
- `dry_run`: bool (propose only, do not create Issues; default false for apply mode).
- `include_defaults`: bool (incorporate platform + extension default informational goals; default true).

**Outputs** (structured, agent-friendly):
- `proposed_questions`: array of objects with:
  - `title` (for the Question Issue)
  - `body` (full template: goal statement, sample questions, provenance, links to artifacts to update, suggested `answer_signal`)
  - `related_goals`: array of references to Goals on the Wiki page
  - `provenance`: where the gap was detected (specific file/issue/discussion + excerpt)
  - `priority_rationale`: why this gap matters to the Goals
  - `refinement_note`: how this could be narrowed in follow-ups
- `existing_gaps_addressed`: count or list of prior Questions that were refined/closed as part of this audit.
- `audit_log`: human-readable summary of surfaces scanned, signals used (including Goals page), decisions made.
- `next_actions`: recommended follow-ups (e.g., "Present top 3 via /qanda", "Create blocking Question if needed").

**Behavior Rules (enforceable contract)**:
1. **Open-ended by default**: Always start broad unless scoped. Use the Wiki `Goals` page (if present) as a primary strategic signal, but treat it as *one* input among many (code patterns, open issues, PR discussions, existing Questions, bootstrap defaults, etc.). Never assume the Goals page is the *only* source.
2. **Provenance & Traceability**: Every proposed Question must include clear links back to where the gap was noticed and forward to artifacts that should be updated on resolution. Use structured comment blocks (e.g., `PLATE-INFORMATIONAL-GOAL`) compatible with the Answer Model.
3. **Continuous Refinement**: Generated Questions should support follow-up (broad → specific). The audit can detect and link related prior Questions.
4. **Quality over Quantity**: Prefer fewer, high-signal Questions. Use heuristics + LLM reasoning (via the agent's own capabilities) to avoid noise. Cap via `max_questions`. Agents should prioritize and synthesize.
5. **Specialized Scoping**: When `agent_type` is provided (or inferred from persona), narrow the surface and heuristics (e.g., marketing agent focuses on positioning, users, GTM gaps; engineering agent on architecture, risks, unknowns in code).
6. **Platform Defaults + Extensibility**: Always include relevant platform/extension default informational goals (see #222). Extensions register via catalog or manifest; core audit incorporates them when in scope.
7. **Integration with Existing Flows**: Generated Questions feed directly into Curiosity/Q&A, Contemplation Engine (#149), and blocking/resumption (#147/#148). The audit itself can be triggered from `plate_record_answer` or as a standalone tool.
8. **No Data Loss / Auditability**: Full log of the audit run. Respect existing invariants (never lose info, agents can find answers, users can revise, every answer drives progress).
9. **Human-in-the-Loop Friendly**: Dry-run mode for review. Agents post proposed Questions as comments or draft Issues for human approval before creation when appropriate. Escalate ambiguity.
10. **Wiki as Strategic Home**: The `Goals` page (per #219 convention) is the preferred location for high-level mission. Audits should encourage its adoption if missing (light nudge via health or output).

**CLI Surface** (`gh plate info-audit` or similar, thin wrapper over the MCP tool):
- Supports `--dry-run`, `--scope`, `--json`, interactive mode for presenting/synthesizing proposals.
- Integrates with existing `gh plate qanda` for follow-up.

## Platform Integration Points

- **Bootstrap / Onboarding** (#224): Offer to initialize the `Goals` wiki page (using the convention from #219) when wiki sync is enabled or user indicates strategic planning interest. Seed initial platform defaults as Questions if none exist.
- **Agent Guidance / Personas** (#225): Update `QANDA_CURIOSITY_GUIDANCE` and `plate.agent.md` with explicit sections on performing audits, reading the `Goals` page, generating/refining Questions, and contributing back.
- **Wiki Sync**: The `Goals` page participates in scoped wiki sync (under `docs/wiki/`). Audits respect this.
- **Extensibility** (#226): Extensions register default goals and optional audit heuristics via the baseline catalog or a new manifest. Core engine discovers and incorporates them.
- **Health / Epic Status**: Light integration — e.g., surface "missing Goals page" or "stale audit" signals in `plate_health` or `plate_epic_status`.
- **Contemplation Engine**: The audit can be invoked as part of contemplation or as a standalone "proactive" mode. Generated Questions feed into normal flows.

## Alternatives Considered

- **Fully LLM-driven open discovery (no Goals page reference)**: Rejected — loses grounding in explicit project intent; risks drift or low-relevance Questions.
- **Only default/platform goals (no project-specific discovery)**: Rejected — misses the power of repo-specific audits against the project's own Goals.
- **Heavy structured Goals page (YAML frontmatter required)**: Rejected for v1 (per #219 user direction; start flat/prose, evolve later if agent wins are clear).
- **Per-Epic Goals pages**: Future possibility, but start with repo-level for simplicity and broad applicability.
- **Synchronous only (no async audit tool)**: Rejected — agents need on-demand + continuous modes.

## Decision Criteria

- Does the contract enable high-quality, traceable Questions grounded in real Goals?
- Is it extensible for the ecosystem (platform + extensions)?
- Does it integrate cleanly with existing Curiosity/Contemplation/Answer Model without duplication?
- Is it practical for both general and specialized agents?
- Does it respect PLATE principles (GitHub-native, lightweight, auditable, human judgment preserved)?

## Acceptance Evidence

- A PLATE-adopting project (new or existing) can run `plate_perform_information_audit --dry-run`, review high-signal proposed Questions tied to its `Goals` page + other signals, and apply them.
- Specialized agents (e.g., research vs. marketing personas) produce appropriately scoped results.
- Generated Questions have full provenance, link to Goals and target artifacts, and feed cleanly into Q&A/Contemplation.
- Extension-provided defaults are discoverable and used.
- The convention is documented in the template and adopted by new projects via bootstrap.
- Full audit log is committed or referenced for traceability.

## Open Questions / Future Work

- Exact MCP tool names and schemas (finalize in implementation).
- Performance/cost controls for broad audits (token budgets, surface limits).
- UI/UX for presenting audit results (future TUI enhancement in #151 lineage).
- Taxonomy/classification of Informational Goals (future, for better prioritization/synthesis).
- Automated scheduling of audits (e.g., on new Epic or periodic via GitHub Action).

This design satisfies the platform-level requirements of Epic #218 and provides a clear, implementable contract for the Features that follow (#221, #224, #225, #226, etc.).

---

*Related: #219 (Goals page structure), #220 (concept modeling), #222 (defaults catalog), #224 (convention adoption), Epic #139 (Curiosity foundation).*

Closes #223