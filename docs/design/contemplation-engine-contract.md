# Contemplation Engine Contract & Agent Behavior — Design Spec

- **Issue:** #143
- **Designed by:** (populated via PR #146 babysit cycle addressing devin review threads)
- **Date:** 2026-05-30
- **Status:** Draft

## Problem

Define the precise, enforceable "Contemplation" contract that any agent (especially the plate agent) must follow when a user provides an answer in Q&A mode. This is the core behavioral engine that turns user input into durable progress across the entire PLATE system per the four invariants in Epic #139:
- Never lose user-provided information
- The agent can reliably find previous answers
- Users can revisit, revise, or correct prior answers
- Every answer drives forward progress (new issues, artifact updates, closed Questions only on verified signal)

## Constraints

- Must be deterministic enough for reliable autonomous execution
- Must never lose information (see four invariants)
- Must create forward momentum (the key value of the vision)
- Must be reviewable and auditable by humans
- Must work with existing GitHub issue comments as the source of truth (no external DB)
- Must support both human and autonomous agent answers

## Design Decision

On every user-provided answer to a Question issue surfaced in Q&A mode, the agent MUST execute this exact sequence:

1. **Full transcript append (non-destructive)**: Post a structured comment on the source Question containing:
   - Original question text (verbatim)
   - Verbatim user answer
   - Timestamp + session/provenance (agent login, MCP/CLI context, git commit if any)
   - Link to any prior revision comment (see Answer Model #142)
   Use the provenance schema defined in sibling Design #142. This satisfies "never lose" and enables findability via GitHub search + MCP comment queries.

2. **Create forward-progress artifacts**:
   - Parse the answer against the Question's documented `answer_signal`.
   - If gaps/requirements identified: create appropriately labeled child issue(s) (Feature/Research/Design/Question) with `Closes` or reference back to parent Question + Epic #139.
   - For process-impacting answers: directly prepare updates to AGENTS.md, .agentic/skills.yml, SPEC.md, CURRENT.md, wiki sources, or docs/ as required by those files' rules (always via atomic Documentation or Feature PRs; never direct main push).
   - Update Epic #139 PLATE_SESSION_STATE JSON comment with new children as needed.
   - For research/design answers, commit findings to the standard docs/research/ or docs/design/ locations.

3. **Revision/re-answer handling**: Always append (never mutate prior comments). Re-evaluate the full history + new input; may close stale follow-on issues and/or spawn corrected ones. Preserve full chain for audit.

4. **Closure decision**: Close the Question if and only if the `answer_signal` criteria are verifiably met by the accumulated transcript evidence (agent can cite specific answer excerpts; human confirmation for high-risk). On closure, include the required === USAGE REPORT === block per AGENTS.md.

5. **Persona and guidance updates**: This contract must be encoded in:
   - AGENTS.md Question handling loop and "Third-Party Agent Feedback" / babysit sections
   - plugin/agents/plate.agent.md (and .plugin copy)
   - Baseline agent catalog entries for Curiosity/Q&A capabilities
   - Any `plate_plan_epic` extensions for Q&A session state

The contract composes with existing Research/Design/Feature loops (see AGENTS.md §Required Work Loop) and the babysit flow for PR feedback.

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|--------------|
| Fully free-form agent behavior after receiving an answer | Current informal state; too unreliable, inconsistent progress, violates invariants |
| Only updating the Question + creating one follow-up issue | Too narrow; misses required direct artifact mutations and multi-type issue creation for full value |
| Requiring a human to always approve every new issue | Excessive friction; blocks autonomous vision for informational goals while still allowing human checkpoints where specified (e.g. need:human-review) |

## Artifact

- The formal contract + numbered decision sequence (this document)
- Example flows (e.g. user answers purpose question during bootstrap → Question created + initial research issue + AGENTS.md note)
- Required deltas to AGENTS.md, plate.agent.md, and baseline catalog (to be implemented in feature PRs #149+)
- Cross-references to #142 (storage), #144 (UX), #145 (surfaces)

## Open Questions

- Precise machine-readable encoding of `answer_signal` in Question bodies (potential extension in #147)
- Interaction with plate_plan_epic session JSON for live Q&A state (see #145)

## Acceptance Evidence

- An autonomous agent session executing the contract on a test Question produces: full transcript comment, 1+ new linked issues, artifact updates where warranted, and closure only after signal verification.
- Audit of any closed Question in the Epic shows complete lossless history.
- No violations of the four invariants in verification runs.
- PRs implementing the contract update the required process files atomically.

This design is derived directly from Design issue #143 requirements and Epic #139 invariants. It will incorporate cross-references to the full research inventory artifact from #140 (docs/research/curiosity-qanda-inventory.md) once that Research PR lands. All changes pushed to the existing PR branch per babysit rules.