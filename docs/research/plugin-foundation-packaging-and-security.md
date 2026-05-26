# Plugin Foundation Epic 1 — Packaging and Security Baseline

- **Issue:** #16, #18
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-26
- **Status:** Completed (default recommendation set)

## Research Question

For Epic #14's no-op plugin baseline:

1. What installation strategy should be used first?
2. What trust/security posture is required before adding richer capabilities?

## Sources

- [Creating a plugin for GitHub Copilot CLI — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating)
- [GitHub Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)
- `docs/research/stack-selection.md`

## Findings

### Packaging / installation strategy (Issue #16)

Default recommendation for Epic 1:

- Use **GitHub subdirectory install**:
  - `copilot plugin install akasper/plate_core:plugin`

Rationale:

- Matches documented architecture (`plugin/` surface).
- Avoids forcing immediate release artifact pipeline work.
- Keeps install path explicit while plugin remains scaffold-level.
- Supports fast iteration during Epic 1.

Deferred for later epics:

- Marketplace distribution
- npm/release artifact packaging strategy
- long-term update-channel policy

### Trust/security posture (Issue #18)

Baseline policy for Epic 1:

- Plugin is **declarative-only** (`plugin.json` + no-op agent markdown).
- No credential handling.
- No MCP server process launch.
- No external network/service invocation.
- No filesystem mutation responsibilities introduced by plugin behavior.

Forward policy guardrail:

- Any future addition of skills, hooks, or MCP server definitions should trigger explicit security review before merge.

## Recommendation

Adopt the above defaults as Epic 1 policy:

1. Install from `OWNER/REPO:plugin`.
2. Keep behavior side-effect-free and deterministic.
3. Gate any capability expansion (skills/MCP runtime) behind explicit security/design review in later epics.
