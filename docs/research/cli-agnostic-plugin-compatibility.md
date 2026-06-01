# Research: CLI-Agnostic Plugin Manifest & Agent Definition Compatibility

**Issue:** #203 (part of Epic #202 / Epic: grok-build)  
**Date:** 2026-06-01  
**Status:** Complete for current state  
**Researcher:** Autonomous grok-build PM loop

## Summary

As of the state on `main` after merge of #238 (and prior autonomous work on the plugin), the PLATE plugin files are already **largely compatible** with standards-compliant CLI agent plugin conventions (beyond GitHub Copilot).

The core files have been made host-agnostic:

- `plugin/plugin.json` — Generic manifest (name, description emphasizing "any compatible CLI agent", agents/ dir, .mcp.json wiring).
- `plugin/agents/plate.agent.md` — Written entirely in terms of the "host agent's native interactive primitives". No Copilot-specific TUI, form, or UI references remain. Strong guidance for Q&A/Curiosity mode, delegation, health/epic status, etc.
- `plugin/.mcp.json` — Minimal and standard (maps to the `plate-mcp` binary).

## Key Findings

### 1. Standard Plugin Manifest Requirements (Claude Code / compatible CLIs)

Common conventions observed across modern CLI agents that support plugins (Claude Code, Cursor, and similar MCP-capable tools):

- A top-level manifest (often `plugin.json` or equivalent) declaring:
  - `name`, `description`, `version`
  - `agents` (directory containing agent definitions)
  - MCP server wiring (frequently a `.mcp.json` or `mcpServers` map pointing to command/binary)
- Agent instruction files in an `agents/` directory (markdown with frontmatter `name:` / `description:` is common and well-supported).
- MCP configuration that is just a command to execute (the `plate-mcp` binary approach is standard and portable).

**Current PLATE state:** Matches this pattern closely. The existing `plugin/plugin.json` and `.mcp.json` are already in a compatible shape.

### 2. Known Incompatibilities / Gaps (as of this research)

- **None blocking** in the current files for basic install + agent loading + MCP tool exposure.
- Minor polish opportunities (non-breaking):
  - Ensure `description` in `plugin.json` remains high-level and benefit-focused (it currently is).
  - The agent definition (`plate.agent.md`) already correctly prefers "native interactive primitives of the host agent" — this is excellent for Grok Build, Claude, Cursor, etc.
  - No hard-coded assumptions about TUI, specific UI components, or Copilot-only surfaces.

### 3. MCP / `plate-mcp` Wiring

The `.mcp.json` simply invokes the `plate-mcp` binary. This is the most portable pattern across CLI agents that support MCP servers. As long as the binary is installed and on PATH (or referenced correctly during `plugin install`), it works for any MCP-capable host.

No Copilot-specific MCP registration remains.

### 4. Agent Instruction File Discoverability & Format

- `agents/plate.agent.md` uses standard frontmatter + markdown body.
- Modern agents (including this Grok Build session and Claude Code) discover and load such files reliably when declared via the manifest.
- The content is already updated to be a good "PLATE core agent" persona that works across hosts (delegation via MCP, health checks, epic status, curiosity/Q&A using host primitives, etc.).

## Recommendations / Input to Feature Work (#205, #206, #207)

1. **Core files (#205 scope):** Current state on main is already a strong baseline for CLI-agnostic. Any remaining changes in #205 should be small polish / explicit compatibility notes rather than large rewrites.
2. **Verification of `plate_plan_epic` (#206):** High value to explicitly test the full flow (Epic creation with correct labels, milestone, sub-issues, epic branch) when invoked from a non-Copilot agent. The agent instructions already guide this correctly.
3. **E2E tests (#207):** Update the existing `tests/e2e/copilot-plugin.spec.ts` (and structure tests) to be host-agnostic or add matrix coverage. Validate that a generic agent install succeeds and the loaded agent behaves as documented.
4. **Documentation:** The plugin README / install instructions should emphasize "works with any standards-compliant CLI that supports the common manifest + agents/ + MCP pattern."

## Conclusion

The heavy lifting to remove Copilot-specific language and adopt host-agnostic patterns has already been performed in prior work on this repository. The current `plugin/` surface is compatible with the documented conventions used by Claude Code and similar MCP-first CLI agents.

**Primary remaining work** under Epic #202 / Epic: grok-build is:
- Formal verification and hardening of key ceremonies (especially `plate_plan_epic`) when used cross-CLI (#206).
- Test updates (#207).
- Any final doc / example polish.

This research artifact unblocks focused Feature work on the remaining children.

## References
- Current files on main (post #238): `plugin/plugin.json`, `plugin/agents/plate.agent.md`, `plugin/.mcp.json`
- Epic #202 and children #203, #205, #206, #207 (all labeled `Epic: grok-build`)
- Related prior research in `docs/research/` (plugin foundation, MCP exposure patterns, etc.)

**Artifact for #203 complete.** Ready for Documentation PR (`Closes #203`).