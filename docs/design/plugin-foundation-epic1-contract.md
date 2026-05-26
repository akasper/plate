# Plugin Foundation Epic 1 — Design Contract

- **Issue:** #15, #17, #19
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Draft (default decision set; may be superseded by human override)

## Problem

Epic #14 needs implementation-level defaults so work can continue without waiting on every design decision.

## Constraints

- Epic 1 must remain intentionally minimal (no skills, no MCP runtime).
- Plugin should be installable and invocable today.
- Decisions should preserve forward compatibility for Epic 2+.

## Design Decision

### 1) Invocation contract (Issue #15)

- Agent ID/name: `plate`
- Invocation path: `/agent plate`
- Required success response (deterministic baseline):
  - `PLATE plugin foundation is installed. This is the no-op baseline for Epic #14; skills and MCP capabilities are planned for future epics.`
- Failure behavior:
  - If invoked outside intended plugin context, agent should still return the same no-op baseline message and avoid side effects.

### 2) Repository layout (Issue #17)

- Adopt dedicated plugin surface at:
  - `plugin/plugin.json`
  - `plugin/agents/plate.agent.md`
- Keep plugin surface declarative; no runtime wiring in Epic 1.
- Reserve future paths:
  - `plugin/skills/` for Epic 2
  - `plugin/.mcp.json` for Epic 3

### 3) Completion evidence + CI policy (Issue #19)

- Definition of done for Epic 1:
  - Plugin manifest exists and is valid JSON.
  - `/agent plate` surface exists via plugin agent file.
  - README includes install + invoke commands.
  - `CURRENT.md` captures implemented plugin scaffold.
- CI policy:
  - Existing PR gates remain required (`Labels`, issue-link check, docs gate, test placeholder, audit).
  - No additional hard gate introduced in Epic 1.
  - Plugin-specific CI hardening is deferred to a follow-up Feature issue.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Add skills/MCP wiring immediately | Violates Epic 1 minimal-scope constraint and increases risk. |
| Root-level `plugin.json` in repo root | Works, but weakens explicit architecture boundary already documented as `plugin/`. |
| Non-deterministic agent response | Makes smoke-test behavior ambiguous and harder to validate. |

## Acceptance Evidence

Implemented in Feature #20 and merged PR #21:

- `plugin/plugin.json`
- `plugin/agents/plate.agent.md`
- README plugin install/invoke instructions
- `CURRENT.md` implemented feature entry
