# MCP Tool Surface for Agents and Skills — Design Spec

- **Issue:** #74
- **Designed by:** Copilot / plate_core automation
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

Agents and skills defined in the baseline catalog must be usable by MCP clients, including Copilot plugins and future orchestration agents. This design specifies every MCP tool exposed for agent and skill discovery and for delegating a task to a single agent, including the full input and output contracts.

## Constraints

- MCP tool payloads must be JSON-serializable and mirror the CLI discovery output (no separate shape).
- Discovery tools must read from the shared `BaselineCatalog` registry; no separate data source.
- The delegation tool must remain stateless in Phase 1: it constructs a structured guidance response without spawning a live agent process.
- Tool names must follow the existing `plate_*` prefix convention already used in `mcp_server.py`.
- Unknown or invalid arguments must return an explicit error payload, not raise an unhandled exception.
- Every tool must appear in the MCP `tools/list` manifest so clients can discover it without prior knowledge.

## Design Decision

### Tool inventory

Five tools are exposed under the `plate_*` namespace:

| Tool name | Purpose |
|---|---|
| `plate_agents` | List all agents (summary records) |
| `plate_agent` | Get full details for one agent |
| `plate_skills` | List all skills (summary records) |
| `plate_skill` | Get full details for one skill |
| `plate_delegate` | Delegate a task to a named agent and receive structured guidance |

### `plate_agents`

Returns the full list of agents from the baseline catalog.

**Input:** none required; accepts optional `surface` filter.

```json
{
  "surface": "mcp"
}
```

**Output:**

```json
{
  "agents": [
    {
      "id": "project-manager",
      "name": "Project Manager",
      "description": "Coordinates project CRUD, backlog grooming, epic framing, and release definition.",
      "primary_skill_ids": ["crud-projects", "groom-backlog", "define-epic", "define-release"],
      "constraints": ["Keep planning outputs concise and actionable.", "..."],
      "surfaces": ["copilot-plugin", "gh-plate", "mcp"]
    }
  ]
}
```

When `surface` is provided, the list is filtered to agents whose `surfaces` list includes the given value.

### `plate_agent`

Returns the full record for a single agent, plus the full definitions of its primary skills resolved from the catalog.

**Input:**

```json
{
  "agent_id": "software-engineer"
}
```

`agent_id` is required. Returns an error payload if the ID is not found.

**Output:**

```json
{
  "id": "software-engineer",
  "name": "Software Engineer",
  "description": "Implements product changes, reviews test coverage, and fixes broken builds.",
  "primary_skill_ids": ["review-test-coverage", "fix-broken-build", "audit-spec-current"],
  "constraints": ["Make small, test-driven changes.", "Preserve behavior unless a change is explicitly intended."],
  "surfaces": ["copilot-plugin", "gh-plate", "mcp"],
  "resolved_skills": [
    {
      "id": "review-test-coverage",
      "name": "Review Test Coverage",
      "description": "...",
      "inputs": ["Change diff", "Existing tests", "Risk areas"],
      "outputs": ["Coverage gaps", "Test recommendations"],
      "examples": ["Identify missing tests before adding the baseline catalog loader."],
      "owning_agent_ids": ["software-engineer", "ci-engineer"]
    }
  ]
}
```

### `plate_skills`

Returns the full list of skills from the baseline catalog.

**Input:** none required; accepts optional `agent_id` filter.

```json
{
  "agent_id": "research-agent"
}
```

When `agent_id` is provided, the list is filtered to skills whose `owning_agent_ids` list includes the given value.

**Output:**

```json
{
  "skills": [
    {
      "id": "research-synthesis",
      "name": "Research Synthesis",
      "description": "Consolidate findings from multiple sources into a decision-ready summary.",
      "inputs": ["Research artifacts", "Discussion threads", "Existing design notes"],
      "outputs": ["Synthesis memo", "Decision options"],
      "examples": ["Summarize the evidence for choosing YAML as the baseline catalog source."],
      "owning_agent_ids": ["market-researcher", "research-agent"]
    }
  ]
}
```

### `plate_skill`

Returns the full record for a single skill, including the names of its owning agents resolved from the catalog.

**Input:**

```json
{
  "skill_id": "define-epic"
}
```

`skill_id` is required. Returns an error payload if the ID is not found.

**Output:**

```json
{
  "id": "define-epic",
  "name": "Define Epic",
  "description": "Frame a coherent epic with scope, outcomes, and child issue boundaries.",
  "inputs": ["Problem statement", "Known constraints", "Desired outcome"],
  "outputs": ["Epic summary", "Child issue sketch"],
  "examples": ["Draft an epic for adding baseline agents and skills to plate_core."],
  "owning_agent_ids": ["project-manager"],
  "resolved_agents": [
    {
      "id": "project-manager",
      "name": "Project Manager",
      "description": "Coordinates project CRUD, backlog grooming, epic framing, and release definition."
    }
  ]
}
```

### `plate_delegate`

Accepts an agent ID and a free-text task description. Returns structured guidance: the agent's persona context, relevant skill definitions, and a framed prompt suitable for pasting into a Copilot chat or routing to the agent's surface.

This tool is stateless in Phase 1. It does not spawn a live agent process or call any external API. It constructs a deterministic guidance response from the catalog.

**Input:**

```json
{
  "agent_id": "research-agent",
  "task": "Summarize the evidence for choosing YAML as the baseline catalog source and recommend a decision.",
  "surface": "copilot-plugin"
}
```

- `agent_id` (required): target agent from the baseline catalog.
- `task` (required): free-text task description passed through to the guidance output.
- `surface` (optional): the surface through which the caller intends to invoke the agent (`copilot-plugin`, `mcp`, or `gh-plate`). Defaults to `mcp`.

**Output:**

```json
{
  "agent_id": "research-agent",
  "agent_name": "Research Agent",
  "surface": "copilot-plugin",
  "task": "Summarize the evidence for choosing YAML as the baseline catalog source and recommend a decision.",
  "guidance": {
    "persona_context": "You are the Research Agent. Synthesizes open questions, discussion threads, and evidence into decision-ready findings. Separate source facts from recommendations. Prefer committed artifacts over ephemeral notes.",
    "relevant_skills": [
      {
        "id": "research-synthesis",
        "name": "Research Synthesis",
        "description": "Consolidate findings from multiple sources into a decision-ready summary.",
        "inputs": ["Research artifacts", "Discussion threads", "Existing design notes"],
        "outputs": ["Synthesis memo", "Decision options"]
      }
    ],
    "suggested_invocation": "@research-agent Summarize the evidence for choosing YAML as the baseline catalog source and recommend a decision."
  },
  "status": "ready"
}
```

**Error output (unknown agent):**

```json
{
  "agent_id": "unknown-agent",
  "status": "error",
  "message": "Unknown agent: unknown-agent"
}
```

### Error contract

All tools return an explicit error payload instead of raising unhandled exceptions:

```json
{
  "status": "error",
  "message": "<human-readable description of what went wrong>"
}
```

Callers should check for the `status` key or the absence of the primary result key.

### MCP manifest registration

All five tools are registered in the MCP `tools/list` response. Each entry follows the existing `plate_*` manifest pattern:

```json
{
  "name": "plate_delegate",
  "description": "Delegate a task to a named baseline agent and receive structured guidance.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_id": { "type": "string", "description": "ID of the target agent." },
      "task": { "type": "string", "description": "Free-text task description." },
      "surface": { "type": "string", "enum": ["copilot-plugin", "mcp", "gh-plate"], "description": "Intended invocation surface." }
    },
    "required": ["agent_id", "task"]
  }
}
```

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Separate discovery schema from CLI schema | Creates drift; MCP and CLI payloads must stay in sync. |
| Live agent spawning in `plate_delegate` Phase 1 | Out of scope; stateless guidance is sufficient for experimentation. |
| Single omnibus `plate_catalog` tool | Does not compose well; callers need focused tools for agent-only or skill-only queries. |
| Undeclared tools not in `tools/list` | Breaks MCP client auto-discovery and confuses orchestration agents. |

## Artifact

Implementation lives in `src/plate_core/mcp_server.py` dispatching to `baseline_catalog.py`. The manifest response is built from the same tool list. `plate_delegate` constructs its response from `get_agent()`, its resolved skills, and the provided task string.

## Open Questions

- Should `plate_delegate` accept a `skill_id` override to target a specific skill within an agent rather than defaulting to all primary skills? Deferred until real usage patterns emerge.
- Should a Phase 2 `plate_delegate` wire into a live agent invocation when a `PLATE_AGENT_ENDPOINT` environment variable is set? Tracked as a follow-up feature.

## Acceptance Evidence

- `tools/list` returns manifest entries for all five tools.
- `plate_agents` and `plate_skills` return arrays matching the full baseline catalog.
- `plate_agent` and `plate_skill` return resolved records for every ID in the catalog.
- `plate_agent` and `plate_skill` return an error payload for an unknown ID without crashing the server.
- `plate_delegate` returns a `ready` guidance response for every valid agent ID.
- `plate_delegate` returns an `error` payload for an unknown agent ID.
- CLI and MCP list payloads share the same field names and values for the same catalog entry.
