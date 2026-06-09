# Narrow Delegation Packets and Short Sub-Agent Prompts — Design Spec

- **Issue:** #395
- **Designed by:** @copilot
- **Date:** 2026-06-08
- **Status:** Draft

## Problem

PLATE's current delegation model is conceptually correct: it uses routing-by-metadata rather than subprocess orchestration. The remaining cost problem is that the delegated handoff is still centered on a broad `delegation_prompt` string. That encourages agents to pass too much context, re-explain repository rules, and leave the target agent to rediscover scope and success conditions.

The delegation unit should become a **narrow task packet**, not a prose dump.

## Constraints

- Build on the existing `plate_delegate_to_agent` flow and catalog-driven metadata.
- Remain compatible with `gh plate`, MCP, and host-agent surfaces.
- Preserve deterministic prompt generation; do not require an LLM to construct the packet.
- Work with the layered context architecture from #394: delegated work should point to scoped discovery guidance, not copy large policy blocks.
- Keep the format JSON-serializable and stable enough for tests.

## Design Decision

Replace the delegation-centered prompt model with a **packet-centered delegation contract**:

1. the server returns a structured task packet,
2. the packet contains only the minimum context needed to act safely,
3. a short rendered prompt can still be derived from the packet for host agents that need text,
4. deeper repository guidance is referenced through scoped retrieval hints instead of copied inline.

### Packet structure

```json
{
  "agent_id": "research-agent",
  "agent_name": "Research Agent",
  "task": {
    "summary": "Compare two documentation discovery approaches",
    "kind": "research",
    "success_signal": "Recommend one approach with explicit tradeoffs and citations",
    "scope": [
      "agent-facing docs",
      "CLI/MCP discovery surfaces"
    ],
    "out_of_scope": [
      "implementation changes",
      "workflow-file edits"
    ]
  },
  "artifacts": {
    "authoritative": [
      "docs/design/cost-control-layered-agent-context-architecture.md"
    ],
    "working_set": [
      "plugin/agents/plate.agent.md",
      ".github/copilot-instructions.md"
    ],
    "references": [
      "docs/research/cost-control-doc-discoverability-audit.md"
    ]
  },
  "retrieval_hints": {
    "concern": "delegation",
    "first_steps": [
      "Read the authoritative design artifact",
      "Use catalog/tool surfaces before broad prose search"
    ]
  },
  "constraints": [
    "Do not restate broad repository rules unless directly relevant",
    "Keep the response scoped to the delegated task"
  ],
  "invocation_hints": {
    "copilot_plugin": "Select the target agent and paste the rendered short prompt",
    "gh_plate": "gh plate agents show research-agent",
    "mcp": "Call plate_agent with agent_id=research-agent"
  }
}
```

### Core design rule

**The packet is primary; the prompt is a rendering.**

The system should no longer treat the long prose prompt as the canonical handoff artifact. Instead:

- packet fields carry the durable meaning,
- the prompt is derived for surfaces that need text,
- future clients may consume the packet directly without going through a prose wrapper.

### Required packet fields

| Field | Purpose |
|---|---|
| `agent_id` / `agent_name` | target identity |
| `task.summary` | one-sentence delegated objective |
| `task.kind` | coarse routing type (`research`, `design`, `implementation`, `triage`, etc.) |
| `task.success_signal` | explicit done signal |
| `task.scope` | what the agent should focus on |
| `task.out_of_scope` | what the agent must not widen into |
| `artifacts.authoritative` | must-read truth sources |
| `artifacts.working_set` | likely files/docs for direct work |
| `retrieval_hints` | how to rehydrate context without broad scanning |
| `constraints` | target-agent-specific guardrails |

### Optional packet fields

| Field | Purpose |
|---|---|
| `artifacts.references` | background reading only if needed |
| `repo_state` | explicit dynamic state only when essential |
| `dependencies` | upstream issue/PR/design dependencies |
| `handoff_notes` | short transition notes from delegating agent |

## Packet construction rules

### 1. Prefer scoped artifacts over global instructions

If the delegated task is about one capability or issue, the packet should point to the smallest authoritative artifact set that answers it. It should not include generic reminders about the entire repository unless directly required.

### 2. Encode success criteria explicitly

The target agent should not have to infer what "done" means from surrounding prose. A short `success_signal` reduces both ambiguity and follow-up turns.

### 3. Keep repository policy behind retrieval hints

If the delegated task may touch process-sensitive work, include a retrieval hint such as:

- concern: `process / ceremony`
- first step: `consult AGENTS.md section ...`

Do not inline large sections of `AGENTS.md`.

### 4. Separate must-read from may-read

The packet should distinguish:

- **authoritative** artifacts: read first
- **working set**: likely execution surfaces
- **references**: background only if needed

This prevents target agents from treating all linked material as equally urgent.

### 5. Support task-kind defaults

PLATE should support task-kind-specific defaults in the future:

| Task kind | Default emphasis |
|---|---|
| `research` | question, sources, decision criteria |
| `design` | constraints, alternatives, artifact target |
| `implementation` | acceptance criteria, tests, changed surfaces |
| `triage` | current state, reproduction, next action |

The first version can keep one shared envelope while still including `task.kind` so packet renderers can evolve safely.

## Prompt rendering

For text-only surfaces, render a short prompt from the packet:

```text
Act as the Research Agent.

Task: Compare two documentation discovery approaches.
Success signal: Recommend one approach with explicit tradeoffs and citations.
Scope: agent-facing docs; CLI/MCP discovery surfaces.
Out of scope: implementation changes; workflow-file edits.

Authoritative artifacts:
- docs/design/cost-control-layered-agent-context-architecture.md

Working set:
- plugin/agents/plate.agent.md
- .github/copilot-instructions.md

If more context is needed, follow retrieval hints for concern: delegation.
```

This is intentionally much shorter than a broad repository prompt. The packet carries the richer structure if the client can consume it.

## Interaction with the layered context architecture

This design depends on #394:

- delegation packets should carry a **concern** and **retrieval_hints**,
- those hints should point to the canonical context map once it exists,
- packets should not recreate a second discovery system inside delegation.

Together, #394 and #395 create the rule:

> Global guidance lives in the context architecture; delegated work carries only the narrow slice needed for the task.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Keep the current `delegation_prompt` as the main artifact | Too easy to widen scope and too hard to validate structurally |
| Remove prompts entirely and return only raw JSON | Some host agents still need a text handoff surface |
| Create separate packet formats per target agent | Increases drift and makes tests harder; one shared envelope is better initially |
| Include full repository policy in every packet | Defeats the cost-control goal |
| Let the delegating LLM free-write the packet each time | Non-deterministic and hard to test |

## Artifact

### Delegation lifecycle under the new design

```text
delegating agent
      |
      v
 build narrow task packet
      |
      +--> structured output for MCP / CLI
      |
      +--> short rendered prompt for text-oriented clients
      |
      v
 target agent follows retrieval hints only if needed
```

### Migration path

1. Add packet fields alongside the current response shape.
2. Render the current `delegation_prompt` from the packet instead of building it independently.
3. Update CLI/MCP/agent surfaces to prefer packet semantics.
4. Trim the rendered prompt once downstream consumers rely on the packet fields.

## Open Questions

- Should `retrieval_hints.concern` be free text or a closed enum aligned to the context map?
- How much live repository state should ever be embedded in a packet versus looked up on demand?
- Should packet builders infer `working_set` automatically from issue/design metadata in a future version?

## Acceptance Evidence

This design is implemented correctly when follow-up work delivers all of the following:

1. Delegation returns a structured packet with explicit scope, out-of-scope, and success signal fields.
2. The rendered text prompt is materially shorter than the current free-form delegation prompt for the same task.
3. Delegated agents can rehydrate only the context they need by following retrieval hints.
4. CLI, MCP, and host-agent surfaces can all consume the same underlying packet model.
5. Packet construction remains deterministic and testable.
