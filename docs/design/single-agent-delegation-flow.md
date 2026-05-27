# Minimal Single-Agent Delegation and Interaction Flow — Design Spec

- **Issue:** #76
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-27
- **Status:** Draft (to be implemented in Issue #83)

## Problem

While full multi-agent orchestration is out of scope, the Epic requires basic delegation to a single
agent so that users and future orchestration systems can send a task to a specific baseline agent and
receive actionable routing guidance.

The goal is a minimal, consistent delegation flow across the Copilot plugin, MCP server, and `gh plate`
CLI surfaces.

## Constraints

- Delegation must not spin up a subprocess or require agent runtime infrastructure.
- The delegated agent persona is defined in the catalog and rendered from it — no duplication.
- The flow must work identically regardless of which surface initiates it (plugin / MCP / CLI).
- Results must be JSON-serializable so the CLI `--json` contract is preserved.
- The implementation must be testable without a live GitHub or Copilot session.

## Design Decision

### What Delegation Means in plate_core v1

In v1, "delegation" means **routing-by-metadata**: given an agent id and a task description, the system
returns everything needed for a consumer (human or orchestrator) to invoke that agent correctly.

It does **not** mean:
- Spawning a subprocess
- Making outbound API calls on behalf of the task
- Maintaining session state between delegation calls

This keeps the delegation surface stateless, testable, and consistent across all three surfaces.

### Delegation Inputs

```
agent_id:          str  — which baseline agent to delegate to
task_description:  str  — free-text description of what the agent should do
```

### Delegation Output Shape

```json
{
  "agent_id": "research-agent",
  "agent_name": "Research Agent",
  "agent_description": "Performs targeted research...",
  "task_description": "Summarize available MCP server frameworks in Python",
  "delegation_prompt": "You are acting as the Research Agent for this task:\n\nSummarize available MCP server frameworks in Python\n\nRelevant skills: research-synthesis, identify-market-gaps-and-opportunities\nConstraints:\n- Ground recommendations in observed signals or linked artifacts.\n- Distinguish evidence from inference.\n\nProceed with the task.",
  "relevant_skills": [
    {"id": "research-synthesis", "name": "Research Synthesis", ...}
  ],
  "surfaces": ["copilot-plugin", "gh-plate", "mcp"],
  "invocation_hints": {
    "copilot_plugin": "Select the 'research-agent' agent in the Copilot agent picker and paste the delegation prompt.",
    "gh_plate": "gh plate agents show research-agent",
    "mcp": "Call plate_delegate_to_agent with agent_id=research-agent and your task."
  }
}
```

### Flow Across Surfaces

#### Copilot CLI Plugin Flow

```
User → Copilot agent picker → selects 'plate' agent
User: "Delegate this research task to the research-agent: summarize MCP frameworks"
  → plate agent calls MCP tool: plate_delegate_to_agent(agent_id="research-agent", task_description="...")
  → plate_delegate_to_agent returns DelegationInstructionDict
  → plate agent presents delegation_prompt and invocation_hints to user
  → User switches to 'research-agent' picker entry and pastes delegation_prompt
```

#### MCP Client Flow (Orchestration)

```
Orchestrator calls: plate_delegate_to_agent(agent_id=X, task_description=Y)
  → Server returns DelegationInstructionDict
  → Orchestrator uses delegation_prompt as system prompt for next turn
  → Orchestrator routes tool calls to the target agent's declared tools
```

#### `gh plate` CLI Flow

```bash
$ gh plate agents delegate research-agent --task "Summarize MCP frameworks" --json
{
  "agent_id": "research-agent",
  "delegation_prompt": "...",
  "relevant_skills": [...],
  "invocation_hints": {...}
}

# Human-readable variant
$ gh plate agents delegate research-agent --task "Summarize MCP frameworks"
Delegating to: Research Agent (research-agent)
Task: Summarize MCP frameworks

Delegation prompt:
  You are acting as the Research Agent for this task:
  Summarize MCP frameworks
  ...

To use in Copilot: Select 'research-agent' in the agent picker.
To query via CLI:  gh plate agents show research-agent
```

### `delegation_prompt` Generation

The prompt is assembled deterministically from catalog data:

```python
def build_delegation_prompt(agent: BaselineAgent, task: str, skills: list[BaselineSkill]) -> str:
    skill_names = ", ".join(s.name for s in skills)
    constraints = "\n".join(f"- {c}" for c in agent.constraints)
    return (
        f"You are acting as the {agent.name} for this task:\n\n"
        f"{task}\n\n"
        f"Relevant skills: {skill_names}\n"
        f"Constraints:\n{constraints}\n\n"
        "Proceed with the task."
    )
```

No LLM call is needed to generate the delegation prompt — it is assembled from the static catalog.

### Agent Selection / Suggestion (Future)

A `plate_suggest_agent` tool (out of scope for v1) would accept only a `task_description` and return
the most relevant agent using keyword/tag matching against catalog descriptions and examples. This
could be added to v2 without changing the v1 delegation contract.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Subprocess-based agent execution | Requires agent runtime, auth, and process management — too heavy for v1 |
| LLM-based agent routing | Non-deterministic, requires inference budget, hard to test |
| Separate delegation service | Operational overhead; single-server model is sufficient |
| Delegation via GitHub Actions dispatch | Slow feedback loop; wrong surface for conversational routing |

## Artifact

Implementation targets:
- `src/plate_core/baseline_catalog.py` — add `build_delegation_prompt()` and `DelegationResult`
- `src/plate_core/cli.py` — add `gh plate agents delegate <id> --task "..." [--json]`
- `src/plate_core/mcp_server.py` — add `plate_delegate_to_agent` tool
- `plugin/agents/plate.agent.md` — add delegation workflow step
- `tests/test_baseline_catalog.py` — delegation prompt generation tests
- `tests/test_cli.py` — CLI delegation command tests
- `tests/test_mcp.py` — MCP delegation tool tests

## Open Questions

None blocking v1.

## Acceptance Evidence

- `plate_delegate_to_agent(agent_id, task_description)` returns a `DelegationInstructionDict` with all required keys.
- Unknown `agent_id` returns `isError: true`.
- `gh plate agents delegate <id> --task "..." --json` produces the same payload as the MCP tool.
- `delegation_prompt` contains the agent name, task description, and at least one relevant skill.
- `invocation_hints` contains all three surface keys: `copilot_plugin`, `gh_plate`, `mcp`.
- Plugin `.agent.md` instructs the plate agent to call `plate_delegate_to_agent` on delegation requests.
