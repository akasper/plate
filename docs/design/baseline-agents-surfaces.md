# Baseline Agents and Skills — Discovery Surfaces

- **Issue:** #73, #75
- **Designed by:** Copilot / plate_core automation
- **Date:** 2026-05-27
- **Status:** Draft

## Problem

The same baseline catalog needs to be discoverable from the Copilot plugin bundle, the `gh plate` CLI, and MCP so users and automation can find the available agents and skills without relying on private implementation details.

## Constraints

- The plugin bundle already ships declarative agent and MCP surfaces.
- CLI commands should remain JSON-first for automation.
- MCP responses should mirror CLI payloads instead of inventing a separate shape.
- Discovery should work without requiring users to inspect source files manually.

## Design Decision

### Plugin surface

- Keep the Copilot plugin bundle declarative.
- Add one `.agent.md` file per baseline agent under the plugin agent directory.
- Keep the plugin MCP manifest as the single entry point for the `plate-mcp` server.
- Mirror the bundle into both `plugin/` and `.plugin/` so local packaging and install-time packaging stay aligned.

### CLI surface

Add discovery commands under `gh plate`:

- `gh plate agents list`
- `gh plate agents show <agent-id>`
- `gh plate skills list`
- `gh plate skills show <skill-id>`

Each command should support `--json` and print a stable machine-readable payload.

### MCP surface

Expose matching tools that return the same catalog payloads as the CLI:

- `plate_agents`
- `plate_agent`
- `plate_skills`
- `plate_skill`

That keeps the CLI and MCP surfaces in sync and avoids duplicating discovery logic.

### Output contract

- List commands return summary records only.
- Show commands return the full record plus any resolved references.
- Errors should be explicit: missing ID, unknown schema version, or invalid catalog should fail loudly.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Separate registries per surface | Too easy to drift and impossible to keep consistent at scale. |
| Hidden discovery via free-form prompts only | Not automation-friendly and hard to validate. |
| Browser-only or transcript-only discovery | Too brittle for a core repository surface. |

## Artifact

The implementation should wire one catalog into three surfaces:

1. Copilot plugin agent files
2. `gh plate` list/show commands
3. MCP discovery tools

## Acceptance Evidence

- The plugin bundle contains the baseline agent files.
- `gh plate agents/skills` can enumerate the catalog with JSON output.
- MCP returns the same entities and IDs as the CLI.
- The CLI and MCP outputs are derived from the same catalog source.
