---
spec_version: "0.1"
process_version: "PLATE 0.6"
owner: "akasper"
updated_at: "2025-05-27"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is human-owned and agent-assisted. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change.

## Vision

`plate_core` is a single-binary, multi-surface library that makes PLATE project state inspectable, actionable, and agent-accessible from any interface. It is the runtime layer that connects human developers and AI agents to the live health, structure, and operating rules of any PLATE repository.

The project ships in two forms from one codebase: a `gh` extension (`gh plate`) for human and scripted terminal use, and an MCP server (`plate-mcp`) that exposes the same capabilities as first-class AI tools callable via Copilot CLI's `/mcp` command. Future surfaces (VS Code extension, Raycast, CI step) are additive; the core library does not change.

## Users and Personas

| Persona | Need | Success Signal |
|---|---|---|
| PLATE project developer (human) | Quickly check project health, epic status, and what to work on next — without leaving the terminal | `gh plate health` prints a pass/warn/fail summary in under 2 seconds |
| AI agent (Copilot, Devin, etc.) | Call PLATE platform tools natively as structured tool invocations, not shell parsing | `plate-mcp` tools return typed JSON that the agent can act on without prompt engineering |
| PLATE platform maintainer | Ship improvements to both surfaces from a single codebase without divergence | Changes to `pkg/health/` flow through both `gh plate health` and the MCP `plate_health` tool |
| PLATE new-project operator | Bootstrap a new PLATE repo correctly with minimal manual steps | `gh plate bootstrap` covers labels, branch protection, wiki initialization, and first-Epic creation |

## Goals

| Goal | Rationale | Traceability |
|---|---|---|
| Single library, two surfaces | Prevent drift between `gh plate` and `plate-mcp` behavior | Research issue — stack selection |
| PLATE health check at project level | Core value proposition: instant visibility into project PLATE compliance | Epic: plate-core-v1 |
| Epic and issue state queries | Agents need structured project state to plan autonomously without reading raw Issues | Epic: plate-core-v1 |
| Optional-feature detection | `plate_core` must surface which PLATE progressive features are active so agents and humans know what automation is available | Epic: plate-core-v1; Design #39 on plate_template |
| Bootstrap assistance | Reduce manual new-project setup steps to near-zero | Epic: plate-core-v1 |
| Zero-dependency binary distribution | `gh plate` and `plate-mcp` must be installable in devcontainers, CI, and developer machines without a language runtime | Research issue — stack selection |

## Non-Goals

| Non-Goal | Reason |
|---|---|
| Storing project state | `plate_core` is stateless; all state lives in GitHub — no database, no local files beyond config | 
| Being a project management UI | Human-facing output is intentionally minimal; full PM UI is out of scope |
| Replacing GitHub CLI | `plate_core` augments `gh`; it does not reimplement `gh` commands |
| Supporting non-PLATE repositories | `plate_core` queries are specific to PLATE label taxonomy and workflow conventions |

## Target Workflows

| Workflow | Desired Behavior | Evidence Expected When Implemented |
|---|---|---|
| `gh plate health` | Returns a structured health summary: label coverage, branch protection, open epic count, stale issue count, and detected optional features. Exits non-zero if any required gate fails. | Unit tests mocking GitHub API; integration test against a real PLATE repo; `CURRENT.md` entry |
| `gh plate epic status` | Lists open Epics with child issue breakdown (open / closed / blocked), auto-merge queue length, and next recommended action. | Unit tests; manual verification |
| `gh plate features` | Detects which optional PLATE features are configured (e.g., `COPILOT_TRIGGER_PAT`, `AUTONOMOUS_MODE` file) and prints a feature table. | Unit tests; verified against `plate_template` |
| `gh plate bootstrap` | Guides a new PLATE project through label sync, branch protection, wiki init, and first-Epic creation. Interactive TUI (gum) for human use; silent/non-interactive mode for CI. | End-to-end test against a throwaway repo |
| MCP `plate_health` tool | Same as `gh plate health` but returns typed JSON for AI agent consumption via `/mcp` in Copilot CLI. | MCP protocol compliance test; verified Copilot CLI tool call |
| MCP `plate_epic_status` tool | Same as `gh plate epic status` but returns structured data. | MCP protocol compliance test |
| MCP `plate_query` tool | Generic PLATE-aware GitHub query: "what issues are ready to work?", "what is blocked?", etc. | MCP protocol compliance test; verified via Copilot CLI session |

## Constraints

- **GitHub API only** — no external databases, no filesystem state beyond a config file. All queries go to the GitHub REST or GraphQL API.
- **Single binary** — both surfaces must ship as a single compiled binary (or `npx`-runnable package). No runtime dependencies (Node, Python, Go) required in target environments.
- **PLATE label taxonomy** — all queries assume PLATE standard labels. Repos without PLATE labels will get degraded/partial results, not errors.
- **Rate limits** — queries must be designed to stay well within GitHub API rate limits for typical project sizes (< 100 Issues, < 10 Epics).
- **Secret safety** — `plate_core` never reads or logs secret values; it only detects presence/absence of named secrets/variables via the GitHub Secrets API.

## Public Claims

| Claim | Status | Evidence |
|---|---|---|
| `gh plate health` runs in under 2 seconds | Planned | Performance test once core is implemented |
| Single codebase powers both `gh` extension and MCP server | Planned | Architecture verified in Research issue |
| Zero runtime dependencies | Planned | Depends on stack selection — Research issue |

## Open Questions

| Question | Owner | Needed By | Resolution Path |
|---|---|---|---|
| Which language/runtime provides the best balance of `gh` extension support, MCP server support, and zero-dependency binary? | akasper | Before first Feature issues open | Research issue on plate_core |
| Should `plate-mcp` be distributed as `npx plate-mcp` (npm package) or as a binary release alongside the `gh` extension? | akasper | Before v1 release | Research issue |
| How does `gh plate bootstrap` handle repos that already have partial PLATE setup? | TBD | Before `bootstrap` Feature issue | Design issue |

## External Integrations

| Integration | Provider | API Type | Required Credentials | Where to Get Access | Known Constraints / Blockers |
|---|---|---|---|---|---|
| GitHub REST API | GitHub | REST v3 / JSON | `gh` auth token (user's existing `gh` session) or `GITHUB_TOKEN` in CI | `gh auth login` | Subject to secondary rate limits; unauthenticated requests are not supported |
| GitHub GraphQL API | GitHub | GraphQL v4 | Same as REST | Same as REST | Some queries (e.g., project fields) require GraphQL; keep both clients |
| GitHub Secrets API | GitHub | REST v3 | Repo-level `secrets:read` permission (PAT or Actions token) | Per-repo permission grant | Secrets API returns names only — never values |

> **Agent instruction:** Before opening any Feature issue that depends on an external API, verify the integration entry above is complete and the API is reachable. If API availability is uncertain, open a Research issue first.
