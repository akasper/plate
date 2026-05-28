# MCP Tool Surface for Agents and Skills — Design Spec

- **Issue:** #74
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-27
- **Status:** Approved (implemented in PR #85; delegation tool implemented in #83)

## Problem

Agents and skills defined in the baseline catalog must be usable by MCP clients — including the Copilot
CLI plugin and future orchestration agents — through a consistent, discoverable, JSON-RPC tool surface.

## Constraints

- All MCP tools must appear in `tools/list` so LLM clients can discover them at session start.
- Tool descriptions must follow the "Call this when…" pattern for reliable LLM routing (see `docs/research/copilot-cli-friendly-agent-skill-definitions.md`).
- Tool payloads must mirror the CLI `--json` output exactly; no separate wire format.
- Tools must be stateless; all state comes from the YAML catalog loaded at startup.
- The MCP server must remain a single stdio process with no external dependencies beyond `plate_core`.

## Design Decision

### Tool Inventory

#### Discovery Tools (shipped in PR #85)

| Tool Name | Purpose | Required Params | Returns |
|---|---|---|---|
| `plate_agents` | List all baseline agents | none | `{"agents": [AgentDict, ...]}` |
| `plate_agent` | Get one agent by id | `agent_id: str` | `AgentDict` |
| `plate_skills` | List all baseline skills | none | `{"skills": [SkillDict, ...]}` |
| `plate_skill` | Get one skill by id | `skill_id: str` | `SkillDict` |

#### Delegation Tool (Issue #83)

| Tool Name | Purpose | Required Params | Returns |
|---|---|---|---|
| `plate_delegate_to_agent` | Route a task to a specific baseline agent | `agent_id: str`, `task_description: str` | `DelegationInstructionDict` |

#### Supporting Tools (already shipped)

| Tool Name | Purpose |
|---|---|
| `plate_health` | Repository health summary |
| `plate_epic_status` | Epic and child issue status |
| `plate_features` | Optional feature detection |
| `plate_bootstrap` | Bootstrap planning/apply |
| `plate_plan_epic` | Interactive epic planning stub |

### Tool Description Quality Standard

Every agent/skill tool description follows the pattern:

```
"<What it returns>. Call this when <common user intents / LLM routing cues>."
```

Example for `plate_agents`:
```
"Return the full list of baseline plate agents with their names, descriptions, and primary skill ids.
 Call this when the user asks what agents are available, which agent handles a task, or wants an
 overview of the plate agent catalog."
```

### Response Shape

**AgentDict:**
```json
{
  "id": "project-manager",
  "name": "Project Manager",
  "description": "Coordinates project CRUD...",
  "primary_skill_ids": ["crud-projects", "groom-backlog"],
  "constraints": ["Keep planning outputs concise..."],
  "surfaces": ["copilot-plugin", "gh-plate", "mcp"]
}
```

**SkillDict:**
```json
{
  "id": "crud-projects",
  "name": "CRUD Projects",
  "description": "Create, read, update, and delete GitHub projects...",
  "inputs": ["owner/repo identifier"],
  "outputs": ["project list", "project fields"],
  "examples": ["List my projects", "Create a new project for Epic #5"],
  "owning_agent_ids": ["project-manager"]
}
```

**DelegationInstructionDict** (for Issue #83):
```json
{
  "agent_id": "research-agent",
  "agent_name": "Research Agent",
  "task_description": "Find existing solutions for distributed tracing in Python microservices",
  "delegation_prompt": "You are now acting as the Research Agent...",
  "relevant_skills": [{"id": "research-synthesis", ...}],
  "surfaces": ["copilot-plugin", "gh-plate", "mcp"],
  "invocation_hints": {
    "copilot_plugin": "Select the 'research-agent' agent from the Copilot agent picker.",
    "gh_plate": "gh plate agents show research-agent",
    "mcp": "Call plate_agent with agent_id=research-agent"
  }
}
```

### Error Handling

| Error Case | MCP Response |
|---|---|
| Unknown `agent_id` or `skill_id` | `isError: true`, message `"Unknown agent: <id>"` |
| Missing required param | `isError: true`, message listing the missing param |
| Catalog load failure | `isError: true`, message with file path and reason |
| Any unexpected exception | `isError: true`, `str(exc)` — never kill the process |

### `tools/list` Registration

Every tool must appear in the `tools/list` response with a complete `inputSchema`. Required fields
in `inputSchema` must be declared in the `"required"` array so LLM clients know what to pass.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Separate MCP server for agents/skills | Operational complexity with no benefit at this scale |
| GraphQL query surface | Overkill for a catalog of 12 agents; JSON-RPC is sufficient |
| Agent execution via MCP subprocess dispatch | Stateful and requires auth; routing-by-metadata is sufficient for v1 |
| Flattened tool per agent (e.g., `plate_project_manager`) | Explosion of tool names; `plate_delegate_to_agent` handles routing uniformly |

## Artifact

Discovery tools implemented in `src/plate_core/mcp_server.py`.
Delegation tool to be added in Issue #83.
Tests in `tests/test_mcp.py`.

## Acceptance Evidence

- `tools/list` includes `plate_agents`, `plate_agent`, `plate_skills`, `plate_skill`.
- `plate_agents` returns all 12 baseline agents.
- `plate_agent` with a valid id returns the matching agent dict.
- `plate_agent` with an unknown id returns `isError: true`.
- `plate_skills` returns ≥18 skills.
- All tool responses are valid JSON.
- Delegation tool added and tested in Issue #83.
