# Capability, Agent, and Skill Exposure Patterns in MCP Servers and GitHub CLI Extensions

- **Issue:** #68
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

How do MCP (Model Context Protocol) servers, GitHub CLI extensions, and other agentic tooling surfaces currently
expose capability discovery, agent definitions, skill/tool registration, and invocation interfaces?
What patterns govern discoverability, metadata quality, and integration with LLM/agent runtimes?

## Sources

- [MCP specification — modelcontextprotocol.io](https://modelcontextprotocol.io/specification)
- [MCP Python SDK — github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- [GitHub CLI extension authoring — cli.github.com/manual/gh_extension](https://cli.github.com/manual/gh_extension)
- [Custom agents configuration — docs.github.com](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [About custom agents for Copilot — docs.github.com](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-custom-agents)
- `docs/research/custom-agent-packaging.md`
- `src/plate_core/mcp_server.py`
- `src/plate_core/data/baseline_catalog.yml`

## Findings

### 1. MCP: Tools as the Canonical Capability Unit

MCP defines **tools** as the atomic capability unit. Each tool has:

| Field | Purpose |
|---|---|
| `name` | Machine-readable identifier (snake_case conventional) |
| `description` | Human/LLM-readable explanation of what the tool does and when to call it |
| `inputSchema` | JSON Schema object describing required/optional parameters |

Discovery is performed by a `tools/list` request, which returns the full tool inventory in a single round-trip.
There is no native concept of "agent" or "skill" in the MCP spec itself — agents and skills are higher-level
abstractions that *implementations* compose from tools.

**Key pattern: flat tool namespace with rich descriptions.** MCP clients (including LLMs) rely heavily on
`description` quality to route requests correctly. A missing or vague description is effectively a broken surface.

#### MCP Tool Naming Conventions Observed in the Wild

| Convention | Example | Notes |
|---|---|---|
| Verb-noun | `create_issue`, `list_repos` | Most common; action-first |
| Domain prefix | `plate_health`, `plate_agents` | Namespaces tools by product/domain |
| Underscore-separated | `plate_epic_status` | Python/JSON-friendly |

#### Delegation Pattern in MCP

Full agent-to-agent delegation (A2A) via MCP is still evolving. The current pattern for single-agent delegation is:

1. Client calls `tools/list` to discover available delegation targets.
2. Client calls a specific tool (e.g., `plate_delegate_to_agent`) with `agent_id` + `task_description`.
3. Server responds with agent metadata, skill constraints, and a formatted prompt/instruction block.
4. Client uses that instruction to route the conversation to the target agent persona.

This is a *routing-by-metadata* pattern rather than a true subprocess dispatch, which keeps the MCP server stateless.

### 2. GitHub CLI Extensions: Binary-First, No Native Capability Discovery

GitHub CLI extensions (`gh extension install owner/repo`) are thin executable wrappers.
The CLI framework provides no structured capability manifest — discoverability is entirely driven by
documentation (README) and command-line `--help` output.

**Pattern:** Each extension exposes a root command (`gh <extension-name>`) with subcommand trees.
There is no machine-readable capability schema by default.

#### gh plate Enhancement

`gh plate` improves on this pattern by returning **JSON output** (`--json` flag) from every subcommand,
making it composable with scripts and CI automation. The `gh plate agents list` and `gh plate skills list`
commands create a queryable capability manifest at the CLI surface level.

### 3. GitHub Copilot Custom Agents: Declarative Markdown Personas

As documented in `docs/research/custom-agent-packaging.md`, Copilot agents are defined as `.agent.md` files
with YAML frontmatter. Key fields:

```yaml
---
name: <display-name>
description: <purpose — shown in agent picker>
tools:
  - <mcp-tool-name>
  - <built-in-tool>
model: <optional-override>
user-invocable: true
---

<Agent instructions body — up to 30,000 chars>
```

**Discovery mechanism:** The Copilot IDE extension reads `.github/agents/` (repo-scoped),
`<org>/.github/agents/` (org-scoped), and `~/.copilot/agents/` (user-scoped).
Each agent becomes selectable in the agent picker without any runtime registration step.

**Pattern:** Agents are *declarative static files*, not running processes. The LLM interprets the
instructions and uses the declared tools at inference time.

### 4. Other Agentic Tooling Patterns

#### OpenAI Function Calling / Assistants API

Capabilities are registered as **functions** with `name`, `description`, and `parameters` (JSON Schema).
Very similar to MCP tools; the key difference is that OpenAI manages the LLM call loop while MCP leaves
loop management to the client.

#### LangChain Tool Interface

Each tool is a Python object with `name`, `description`, and `_run(input)` method.
Discoverability is code-level (import + instantiate), not protocol-level.
This pattern does not translate well to cross-process or cross-language surfaces.

#### Agent2Agent (A2A) Protocol (emerging)

Google's A2A spec introduces **Agent Cards** — structured JSON documents that describe an agent's
capabilities, communication endpoints, authentication, and skills. This is conceptually close to
`plate_core`'s `baseline_catalog.yml` approach.

Key A2A fields relevant to `plate_core`:

| A2A Field | plate_core Equivalent |
|---|---|
| `id` | `agent.id` |
| `name` | `agent.name` |
| `description` | `agent.description` |
| `skills[]` | `agent.primary_skill_ids[]` |
| `inputModes` | `agent.surfaces[]` |

### 5. Comparison: Discoverability Mechanisms

| Surface | Discovery Mechanism | Machine-Readable? | Schema-Enforced? |
|---|---|---|---|
| MCP | `tools/list` JSON-RPC | ✅ Yes | Partial (inputSchema) |
| gh CLI extension | `--help` text | ❌ No | ❌ No |
| `gh plate` (enhanced) | `gh plate agents list --json` | ✅ Yes | ✅ Via catalog |
| Copilot custom agent | `.github/agents/*.agent.md` frontmatter | ⚠️ Partial (frontmatter) | ❌ No schema validation |
| A2A Agent Card | HTTP endpoint serving JSON | ✅ Yes | ✅ JSON Schema |
| OpenAI Assistants | API registration | ✅ Yes | ✅ JSON Schema |

## Recommendation

1. **MCP tools are the right atomic surface** for plate_core: flat, schema-described, stateless.
   Continue namespacing tools with the `plate_` prefix to avoid collisions.

2. **Catalog-driven metadata** (`baseline_catalog.yml`) gives plate_core an A2A-compatible capability
   description that can be queried from any surface without coupling it to a specific protocol.

3. **Plugin agent files** should reference the catalog indirectly (via MCP tools) rather than
   duplicating metadata — this keeps the `.agent.md` thin and the catalog authoritative.

4. **`gh plate agents list/show`** already provides the machine-readable discovery surface that
   raw `gh` extensions lack. Keep this pattern and extend it to delegation.

5. **For single-agent delegation**, adopt the routing-by-metadata pattern: MCP tool returns agent
   details + formatted delegation prompt. No subprocess dispatch needed at this stage.

### Follow-up Actions

- Design doc for registry and discovery system: Issue #72
- Design doc for MCP tool surface: Issue #74
- Design doc for delegation flow: Issue #76
