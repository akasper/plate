---
spec_version: "0.1"
process_version: "PLATE 0.6"
owner: "akasper"
updated_at: "2026-05-26"
---

# Project Specification

`SPEC.md` describes the desired future state of the project. It is human-owned and agent-assisted. Update this file when the project intent, target users, goals, non-goals, constraints, or major product decisions change.

## Current v1 Implementation Scope

The current implementation baseline delivers:

- `gh plate health` via `gh-plate`
- MCP tool `plate_health` via `plate-mcp`
- installable Copilot CLI plugin scaffold (`/agent plate`)
- baseline agent and skill catalog discovery via `gh plate agents` / `gh plate skills` and matching MCP tools

Other v1-planned capabilities in this specification (epic status, feature detection breadth, bootstrap automation) remain planned until implemented and verified in `CURRENT.md`.

## Vision

`plate_core` is a single-binary, multi-surface library that makes PLATE project state inspectable, actionable, and agent-accessible from any interface. It is the runtime layer that connects human developers and AI agents to the live health, structure, and operating rules of any PLATE repository.

The project ships in three forms from one codebase:

| Surface | Install command | Target user | Invocation style |
|---|---|---|---|
| `gh plate` extension | `gh extension install akasper/plate_core` | Human developers and scripts | Terminal commands (`gh plate health`) |
| `plate-mcp` MCP server | `npx plate-mcp` or binary | AI agents | Structured tool calls via `/mcp` in Copilot CLI |
| Copilot CLI plugin | `copilot plugin install akasper/plate_core` | Copilot CLI conversational sessions | Agent chat (`/agent plate`) |

The **plugin surface** (`plugin/`) bundles a `plate.agent.md` conversational agent that proactively asks project-context questions to achieve PLATE informational goals, discrete skills (e.g., `/skill plate-health`), and an `.mcp.json` config that wires the MCP server into the plugin so the agent has live GitHub data. The plugin directory is declarative (Markdown + JSON only) — the runtime lives in the `plate-mcp` binary.

All three surfaces share the same `pkg/` core library. Future surfaces (VS Code extension, Raycast, CI action) are additive; the core library does not change.

## Users and Personas

| Persona | Need | Success Signal |
|---|---|---|
| PLATE project developer (human) | Quickly check project health, epic status, and what to work on next — without leaving the terminal | `gh plate health` prints a pass/warn/fail summary in under 2 seconds |
| AI agent (Copilot, Devin, etc.) | Call PLATE platform tools natively as structured tool invocations, not shell parsing | `plate-mcp` tools return typed JSON that the agent can act on without prompt engineering |
| Interactive Copilot CLI user | A conversational PLATE assistant that proactively asks the right questions and surfaces project state without the user knowing the right commands | `plate.agent.md` asks "which repo and Epic are you working on?" then calls MCP tools to retrieve live state |
| PLATE platform maintainer | Ship improvements to all three surfaces from a single codebase without divergence | Changes to `pkg/health/` flow through `gh plate health`, the MCP `plate_health` tool, and the plugin agent's tool calls |
| PLATE new-project operator | Bootstrap a new PLATE repo correctly with minimal manual steps | `gh plate bootstrap` covers labels, branch protection, wiki initialization, and first-Epic creation |

## Goals

| Goal | Rationale | Traceability |
|---|---|---|
| Single library, three surfaces | Prevent drift between `gh plate`, `plate-mcp`, and the plugin agent behavior | Research #5 — stack selection |
| PLATE health check at project level | Core value proposition: instant visibility into project PLATE compliance | Epic #4: plate-core-v1 |
| Epic and issue state queries | Agents need structured project state to plan autonomously without reading raw Issues | Epic #4: plate-core-v1 |
| Optional-feature detection | `plate_core` must surface which PLATE progressive features are active so agents and humans know what automation is available | Epic #4; Design #39 on plate_template |
| Bootstrap assistance | Reduce manual new-project setup steps to near-zero | Epic #4: plate-core-v1 |
| Zero-dependency binary distribution | `gh plate` and `plate-mcp` must be installable in devcontainers, CI, and developer machines without a language runtime | Research #5 — stack selection |
| Copilot CLI plugin surface | Conversational agent that proactively asks questions to achieve PLATE informational goals; one-step install bundles agent + skills + MCP wiring | Epic #4; [Copilot CLI plugin docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating) |

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
| Plugin: `plate.agent.md` conversational agent | Agent proactively asks the user which repo and Epic they're working on, then calls MCP tools to retrieve live state and surface actionable next steps. Achieves PLATE informational goals through guided conversation rather than requiring the user to know specific commands. | Verified in a Copilot CLI session: agent asks context questions, calls `plate_health` and `plate_epic_status` tools, returns structured recommendations |
| Plugin: one-step install | `copilot plugin install akasper/plate_core` installs the agent, skills, and MCP server config in one command. | Install test; `/agent` and `/skills list` show plate components; agent can call MCP tools |

## Constraints

- **GitHub API only** — no external databases, no filesystem state beyond a config file. All queries go to the GitHub REST or GraphQL API.
- **Single binary** — all three surfaces must be installable without requiring a language runtime in the target environment. `gh plate` and `plate-mcp` ship as a compiled binary (or `npx`-runnable package); the plugin layer is declarative Markdown + JSON.
- **PLATE label taxonomy** — all queries assume PLATE standard labels. Repos without PLATE labels will get degraded/partial results, not errors.
- **Rate limits** — queries must be designed to stay well within GitHub API rate limits for typical project sizes (< 100 Issues, < 10 Epics).
- **Secret safety** — `plate_core` never reads or logs secret values; it only detects presence/absence of named secrets/variables via the GitHub Secrets API.
- **Plugin agent is conversational, not scripted** — `plate.agent.md` is invoked as `/agent plate` in a Copilot CLI session. It cannot be launched as a one-shot terminal command; that use case belongs to `gh plate`.

## Public Claims

| Claim | Status | Evidence |
|---|---|---|
| `gh plate health` runs in under 2 seconds | Planned | Performance test once core is implemented |
| Single codebase powers `gh` extension, MCP server, and Copilot CLI plugin | Planned | Architecture verified in Research #5 |
| Zero runtime dependencies | Planned | Depends on stack selection — Research #5 |
| Plugin agent proactively surfaces PLATE project state through conversation | Planned | Verified in Copilot CLI session once plugin is implemented |

## Open Questions

| Question | Owner | Needed By | Resolution Path |
|---|---|---|---|
| Which language/runtime provides the best balance of `gh` extension support, MCP server support, and zero-dependency binary? | akasper | Before first Feature issues open | Research #5 |
| Should `plate-mcp` be distributed as `npx plate-mcp` (npm package) or as a binary release alongside the `gh` extension? | akasper | Before v1 release | Research #5 |
| Does the plugin's `plate.agent.md` agent automatically have access to MCP tools declared in the plugin's `.mcp.json`, or does the user need to start the MCP server separately? | akasper | Before plugin Feature issue | Research #5 |
| What is the `.mcp.json` format for pointing to a locally installed binary (the `plate-mcp` server)? | akasper | Before plugin Feature issue | Research #5 |
| How does `gh plate bootstrap` handle repos that already have partial PLATE setup? | TBD | Before `bootstrap` Feature issue | Design issue |

## External Integrations

| Integration | Provider | API Type | Required Credentials | Where to Get Access | Known Constraints / Blockers |
|---|---|---|---|---|---|
| GitHub REST API | GitHub | REST v3 / JSON | `gh` auth token (user's existing `gh` session) or `GITHUB_TOKEN` in CI | `gh auth login` | Subject to secondary rate limits; unauthenticated requests are not supported |
| GitHub GraphQL API | GitHub | GraphQL v4 | Same as REST | Same as REST | Some queries (e.g., project fields) require GraphQL; keep both clients |
| GitHub Secrets API | GitHub | REST v3 | Repo-level `secrets:read` permission (PAT or Actions token) | Per-repo permission grant | Secrets API returns names only — never values |

> **Agent instruction:** Before opening any Feature issue that depends on an external API, verify the integration entry above is complete and the API is reachable. If API availability is uncertain, open a Research issue first.
