---
title: Design: Modeling Informational Goals, Questions, and Project Goals
issue: 220
epic: 218
status: draft
---

# Design: Modeling Informational Goals, Questions, and Project Goals

**Issue:** #220 (Design child of Epic #218 "Information Audit & Goal-Driven Question Generation")

**Designed by:** Grok (xAI)

**Date:** 2026-05-31

**Status:** Draft (for review and refinement)

## Design Goal

Formalize the relationships, distinctions, and artifact mappings for the three core concepts introduced in Epic #218 planning and refined through #219 (Goals page) and #223 (Audit contract). This model must be clear, implementable, and consistent for both human contributors and agents performing Information Audits across any PLATE-adopting project.

## Key Concepts (recap and formalization)

- **Goal**: A high-level, documented statement of project intent and success criteria. Lives primarily on the Wiki `Goals` page (per #219 convention: Mission, Core Principles, How We Intend to Succeed, Current State & Evidence, Open Questions). Broad directional "why we exist + how we win" (including GTM, revenue, deployment, target outcomes). Human- and agent-facing. Not a GitHub Issue.

- **Informational Goal**: A *conceptual need* (not an artifact): "We need to know X in order to achieve (part of) a Goal." Derived from Goals + other signals (code patterns, open issues, discussions, existing Questions, bootstrap defaults). May be implicit until surfaced by an audit. Supports continuous refinement (broad "what is our GTM?" → specific "who is the initial target customer segment and why?") .

- **Question**: The durable GitHub Issue artifact that *encapsulates* one or more Informational Goals. Includes structured body (goal statement, sample questions, provenance, links to artifacts to update, `answer_signal`), labels (Question + area:*), traceability, and closes only with committed evidence per existing PLATE invariants.

These are distinct layers: Goals (strategic source) → Informational Goals (analysis output) → Questions (actionable, trackable artifacts).

## Relationships and Cardinality

- One Goal can spawn 0..N Informational Goals (and over time more as context evolves).
- One Informational Goal typically maps to 1 primary Question (but may contribute to or refine multiple).
- Questions can link to multiple related Goals (via provenance or explicit `related_goals`).
- Refinement: A Question can have child Questions (narrower scope) or be a refinement of a parent Question. Use GitHub issue links + structured markers (e.g. `PLATE-INFORMATIONAL-GOAL-REFINEMENT`).
- Traceability is bidirectional: Question body links back to originating Goal(s)/signals and forward to the required answer artifact(s).

No tight 1:1 enforcement in GitHub; the model is semantic and expressed via conventions in bodies, comments, and labels.

## Where Each Lives (artifact mapping)

| Concept | Primary Home | Secondary / Supporting | Notes |
|---------|--------------|------------------------|-------|
| Goal | Wiki `Goals` page (`docs/wiki/Goals.md` via sync) | SPEC.md (implementation slice of intent), .agentic/ notes | Per #219: lightweight prose, agent-parseable headings. Not in Issues. |
| Informational Goal | Conceptual (in agent reasoning + audit logs) | Structured comment blocks on Questions or audit outputs | Never a standalone artifact; always realized as Question(s). |
| Question | GitHub Issue (type Question via template) | GitHub Projects fields (priority, status, cost class), linked PRs/commits on close | Uses existing `.github/ISSUE_TEMPLATE/question.yml` as base; enhanced for provenance + refinement links. |

## Recommended Question Structure (enhancements to existing template)

Build on the current question.yml (information goal, context, answer_signal, required_artifact, closing checkboxes). Add for Information Audit / modeling support:

- **Provenance section** (in body or structured comment): "Discovered via information audit on <date>; signals: Wiki Goals §Mission, open discussion in #N, code pattern in src/..."
- **Related Goals** (references to Wiki headings or prior answers): e.g. "Supports Goal: Mission (market expansion)"
- **Refinement note**: "This narrows the parent Question #M (broad user research)"
- **PLATE markers** for Answer Model / Contemplation compatibility: `PLATE-INFORMATIONAL-GOAL` blocks (as used in #147/#148 blocking).

Example body sketch (beyond template):

```
## Provenance
Discovered during Information Audit (scope: repo, agent_type: general). Primary signal: Wiki Goals § "How We Intend to Succeed" (revenue via paid tiers).

## Related Goals
- Mission: "..."
- Open Question on Wiki: "..."

## Refinement
Refines parent Question #NNN (broad "understand users").
```

Closing still requires committed artifact + PR with `Closes #N`.

## Continuous Refinement Model

- Audits (and agents) can detect clusters of related open Questions and propose refinements or consolidations.
- When a broad Question is answered, child/narrower Questions may be auto-generated or suggested (via Contemplation or post-answer hook).
- Links use standard GitHub + PLATE comment conventions for machine + human readability.
- No forced hierarchy in GitHub Issues; semantic via body metadata.

## Integration with Existing Systems (#139 lineage + #223 contract)

- **Answer Model**: Questions use/extend `PLATE-ANSWER` and new `PLATE-INFORMATIONAL-GOAL` markers for structured extraction by ContemplationEngine.
- **Blocking / Resumption (#147/#148)**: An Informational Goal can be the root cause for creating a blocking Question; answers unblock via resumption reports.
- **Contemplation Engine**: Audit can run as a "proactive" contemplation mode; generated Questions feed normal prioritization and Q&A flows.
- **Audit Contract (#223)**: `proposed_questions` output uses this model (title/body fields match the template + extensions).
- **Bootstrap / Defaults (#222)**: Default informational goals seed initial Questions using this structure.

## Examples

(Platform-agnostic; applies to any adopter.)

1. Goal (Wiki): "Revenue via self-serve paid tiers within 6 months."
   Informational Goal: "We need to know the top 3 pain points of our current free users that would motivate upgrade."
   Question #NNN: "[Question]: Understand free-user upgrade motivations" (with provenance to the Goal, sample questions, answer_signal = "documented research + pricing experiment plan in docs/", required_artifact = "docs/research/user-upgrade-motivations.md + follow-up issue(s)").

2. Refinement: After partial answer, new narrower Question created linking back as refinement.

## Open Questions / Future Work

- Exact taxonomy for Informational Goals (e.g. categories: market, technical, operational, risk) — deferred to post-v1 after dogfooding.
- Automated detection of refinement opportunities (LLM clustering of open Questions).
- GitHub Projects field standardization for "informational-goal-priority" etc.
- Machine-readable excerpt of Goals page (YAML sidecar?) if agent value proven (per #219 light start).

## Acceptance Evidence

- A design doc exists that unambiguously distinguishes the three concepts and their artifact homes.
- Question template + audit outputs can be shown to follow the model.
- Clear traceability examples in the akasper/plate repo (and template) after #221/#224.
- Integrates without contradiction to #139 machinery and #223 contract.
- **Proving tests** (per Epic #350 Test Coverage Audit convention + Research #361 classification):
  - `tests/test_221_core_audit_engine.py` (PerformInformationAuditTool, catalog goals, Goals page signals, agent guidance integration).
  - `tests/test_curiosity_answers.py` (Answer Model supporting provenance/traceability).
  - (See `docs/audits/test-coverage-audit-initial-inventory-2026-06-06.md` and `docs/research/test-classification-inventory.md` for the full matrix.)

This modeling design provides the conceptual foundation for the core audit engine (#221) and convention adoption (#224). It ensures consistency across the PLATE ecosystem.

---

*Related: #219 (Goals structure), #221 (audit engine), #222 (defaults catalog), #223 (audit contract), Epic #139 (Curiosity/Q&A foundation), Epic #218.*

Closes #220 (Updated for #350/#361 convention dogfooding.)