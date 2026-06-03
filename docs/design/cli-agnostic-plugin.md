# Design: CLI-Agnostic Plugin Manifest and Agent Definition

**Issue:** #204 (part of Epic #202 / Epic: grok-build)  
**Depends on:** #203 (Research complete)  
**Status:** Design artifact for the (already largely achieved) CLI-agnostic state

## Summary

The PLATE `plugin/` surface (`plugin.json`, `agents/plate.agent.md`, `.mcp.json`) has been made compatible with standards-compliant CLI agents (Claude Code, Cursor, Grok Build, and any tool following the common manifest + agents/ dir + MCP server wiring pattern).

This design documents the final generic state and the (minimal) rationale. No large vendor-specific rewrites remain.

## Annotated State (Current on main post #203 research)

### plugin/plugin.json
```json
{
  "name": "plate-core",
  "description": "PLATE core plugin — context-first agent + MCP wiring for any compatible CLI agent.",
  "version": "0.1.0",
  "author": { "name": "PLATE / akasper" },
  "repository": "https://github.com/akasper/plate",
  "license": "MIT",
  "agents": "agents/",
  "mcpServers": ".mcp.json"
}
```

**Changes from any prior Copilot-specific version:** None significant. Description was already broadened. Repository URL is correct and generic.

### plugin/agents/plate.agent.md (core 35-line persona)
- Fully host-agnostic language throughout.
- Explicit preference for "the host agent's native interactive primitives (form inputs, interactive prompts)" for Q&A / Curiosity mode.
- No references to "Copilot TUI", "Copilot form support", or any GitHub Copilot-specific UI.
- Strong, portable guidance for health, epic status, delegation via MCP, features detection, Playwright E2E, etc.
- Reusable sections for QANDA_CURIOSITY_GUIDANCE.

**Rationale:** This directly satisfies the goal of any CLI agent being able to load the persona and behave correctly without special-casing.

### plugin/.mcp.json
```json
{
  "plate-core": {
    "command": "plate-mcp"
  }
}
```

**Changes:** None needed. This is the standard portable MCP server declaration.

## What Does NOT Change (by design)
- The `plate-mcp` binary and all MCP tool implementations (already CLI-agnostic).
- All ceremony logic (plan_epic, health, features, etc.).
- The entire PLATE process, labels, branch model, AGENTS.md conventions, etc.
- Extension model in `.agentic/extensions.yml` (the plugin entry will simply describe the surface as CLI-agnostic).

## Rationale for Minimalism
The research in #203 confirmed that the heavy lifting (removing Copilot-specific language and adopting "host agent native primitives") had already been performed in prior autonomous work on the repository. The current files on main are a strong, compatible baseline.

Any remaining "changes" are documentation, tests, and verification rather than code diffs in the plugin files themselves.

## Next Steps (for sibling issues)
- #205 / #206 / #207 / #208: Verification of `plate_plan_epic`, E2E test updates (remove any remaining Copilot assertions), doc updates, and release-note fragments.
- The design artifact here can serve as the "before/after" reference for those Features.

## Traceability
- Research findings: `docs/research/cli-agnostic-plugin-compatibility.md` (from #203, merged via PR #239)
- This design fulfills the exact "Deliverables" and "Done" signal in #204.

Ready for Documentation PR (`Closes #204`).