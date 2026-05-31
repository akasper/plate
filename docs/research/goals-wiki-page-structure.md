---
title: Research: Wiki Goals Page Structure for Agent and Human Consumption (Platform Convention)
issue: 219
epic: 218
status: complete
---

# Research: Wiki Goals Page Structure for Agent and Human Consumption

- **Issue:** #219 (Research child of Epic #218 "Information Audit & Goal-Driven Question Generation")
- **Researched by:** Grok (xAI), following AGENTS.md Research work loop
- **Date:** 2026-05-31
- **Status:** Complete

## Research Question

What is the optimal structure for a project Wiki `Goals` page that serves as the high-level strategic/mission layer for both humans and agents in the context of the new Information Audit system? How should this convention be defined so that it is effective when adopted by any PLATE project (platform-level, not repo-specific)?

## Sources

- Epic #218 and child tickets (#219-#229)
- Existing PLATE artifacts: SPEC.md (current Goals section and Purpose/North Star), docs/wiki/ (including Curiosity-QA-Mode.md), template_payload/docs/research/information-goals.md and default-questions.md, bootstrap scripts, AGENTS.md (wiki sync rules), docs/design/README.md (wiki sync)
- User clarifications from planning Q&A (Wiki Goals for mission statement "why + how we win"; SPEC for implementation details; light prose structure; platform convention for all adopters; one signal among many for audits)
- Current state of wiki sync and bootstrap in the template

## Findings

### Current State

- High-level intent is currently scattered (SPEC.md Goals for engineering outcomes, default onboarding questions pushing to SPEC, no dedicated strategic mission page).
- Wiki is underused for strategic content; mostly placeholder or synced from docs/wiki/.
- Information goals are handled via Question issues (strong primitive from previous work), but lack a clear upstream "Goals" source for audits to reference.
- Wiki sync is opt-in and scoped; agents must not enable broad writes without approval.

### User Requirements (from planning)
- Wiki `Goals` page: overall mission statement explaining why the project is built and how it will succeed (go-to-market, revenue, deployment, target outcomes).
- Distinct from SPEC.md (keep SPEC's Goals as implementation/engineering layer).
- Structure: lightweight, mostly prose (e.g., Mission, Core Principles, How We Intend to Succeed, Current State & Evidence, Open Questions). Consistent pattern but not heavy machine-readable for v1.
- Platform-level: must work for any PLATE adopter; documented as convention in template; integrated with bootstrap, wiki sync, agent guidance.
- Audits treat it as one important signal (not the sole top-level filter).
- Agent-driven maintenance after initial seeding, with human governance.

### Recommended Convention

The structure and guidance in the draft convention document (created as part of this spike):

- Location: docs/wiki/Goals.md in repo (for source control and wiki sync participation).
- Content: Broad directional mission statements + light rationale/evidence sections.
- Agent use: Read as key strategic input for gap detection during audits; propose updates via Documentation PRs.
- Adoption: Bootstrap can seed it; template docs explain it; wiki sync compatible.

See the created artifact `docs/design/goals-wiki-page-convention.md` in the template_payload for the full recommended convention text (ready for adoption by downstream projects).

### Options Considered
- Heavy machine-readable (YAML frontmatter): Rejected for v1 (per user preference for flat/light; adds complexity without clear agent win yet).
- Purely in SPEC.md: Rejected (user wants separation for strategic vs implementation).
- Per-Epic Goals pages: Possible future, but start with repo-level for simplicity.

### Platform Integration Recommendations
- Update bootstrap to offer seeding the Goals page (when wiki sync enabled).
- Document in template_payload README, onboarding questions design, and wiki sync guidance.
- Add to agent_guidance.py and plate.agent.md so agents expect and use it.
- Wiki sync: Scoped to docs/wiki/Goals.md when enabled.

## Recommendation

Adopt the convention as defined in the draft document. It satisfies agent consumption needs (clear headings, consistent sections, linkable to Questions), human readability, and platform extensibility. Proceed to implementation tickets (#224, #228, #229) to roll it out.

This research closes #219 and provides the foundation for the Goals page in the Information Audit Epic.

## Usage Report

=== USAGE REPORT ===
tokens: 8000
cost: $0.05
duration: 00:15:00
=== END USAGE REPORT ===

Closes #219