# Minimal Single-Agent Delegation Flow — Design Spec

- **Issue:** #76
- **Designed by:** Copilot / plate_core automation
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

While full multi-agent orchestration is out of scope, this Epic must support basic delegation to a single agent so that users and future orchestration systems can experiment with routing tasks to named agents. This design defines the minimal end-to-end flow for selecting an agent, passing a task, receiving results or status, and how this is implemented consistently across the Copilot plugin, MCP server, and `gh` CLI surfaces.

## Constraints

- Phase 1 delegation is stateless: it constructs structured guidance from the catalog but does not spawn a live agent subprocess.
- The flow must be consistent across all three surfaces; no surface invents its own delegation protocol.
- Agent selection must use the catalog ID, not a display name or free-text guess.
- Results must be deterministic given the same input so CI can verify them.
- The full live-agent delegation (Phase 2) is out of scope for this design; this design must be forward-compatible with it.

## Design Decision

### Overview

The minimal delegation flow has four steps:

```
1. Select agent   →  catalog ID lookup via discovery API
2. Pass task      →  task string + optional surface hint
3. Build guidance →  persona context + relevant skills + suggested invocation
4. Return result  →  structured JSON (MCP/CLI) or formatted text (Copilot plugin)
```

This is intentionally thin. The catalog does the work; the runtime does not need to know anything about the agent's domain.

### Step 1: Agent selection

The caller provides an `agent_id` string that must match a catalog entry. This is enforced at the start of the delegation handler — an unknown ID returns an error immediately, before any further processing.

Discovery tools (`plate_agents`, `gh plate agents list`) are the intended path for finding valid IDs. Callers should not hard-code IDs without first consulting the catalog.

### Step 2: Passing a task

The caller provides a free-text `task` description. There is no structure enforced on the task string beyond being non-empty. The guidance response echoes the task string verbatim so the caller can confirm it was received.

An optional `surface` hint (`copilot-plugin`, `mcp`, or `gh-plate`) shapes the `suggested_invocation` string in the response. If omitted, the surface defaults to the channel through which the request arrived.

### Step 3: Building guidance

The handler:

1. Loads the agent record from the registry via `get_agent(agent_id)`.
2. Resolves the agent's `primary_skill_ids` to full skill records via `get_skill()`.
3. Builds a `persona_context` string from the agent's `description` and `constraints`.
4. Builds a `suggested_invocation` string suited to the target surface:
   - Copilot plugin: `@<agent-id> <task>`
   - MCP: a `plate_delegate` call example
   - `gh` CLI: `gh plate delegate --agent <agent-id> "<task>"`
5. Returns a structured guidance payload (see below).

No external calls, LLM inference, or file I/O beyond the catalog read are made during Phase 1.

### Step 4: Result shape

The result is a shared guidance schema used by all three surfaces. Each surface serializes it differently:

```json
{
  "agent_id": "wiki-editor",
  "agent_name": "Wiki Editor",
  "surface": "gh-plate",
  "task": "Draft the wiki page for the baseline agents catalog.",
  "guidance": {
    "persona_context": "You are the Wiki Editor. Writes and synchronizes wiki content so project state stays documented. Preserve traceability back to source artifacts. Avoid inventing undocumented claims.",
    "relevant_skills": [
      {
        "id": "document-new-feature-in-wiki",
        "name": "Document New Feature in Wiki",
        "description": "Write wiki content for a newly shipped feature.",
        "inputs": ["Feature summary", "Implementation notes", "Source links"],
        "outputs": ["Wiki draft", "Traceability notes"]
      }
    ],
    "suggested_invocation": "gh plate delegate --agent wiki-editor \"Draft the wiki page for the baseline agents catalog.\""
  },
  "status": "ready"
}
```

Error cases return:

```json
{
  "agent_id": "<provided-id>",
  "status": "error",
  "message": "<human-readable reason>"
}
```

### Surface-by-surface behavior

#### Copilot plugin surface

1. User opens Copilot chat and selects an agent from the agent picker, or types `@<agent-id>`.
2. The `.agent.md` file for that agent provides the persona instructions natively through Copilot's agent mechanism.
3. For programmatic delegation (e.g., from an orchestration agent), the Copilot plugin calls `plate_delegate` via the MCP tool surface and renders the `guidance.suggested_invocation` to the user.
4. The user or the plugin hands the task off to the agent using the suggested invocation string.

#### MCP surface

1. Caller invokes `plate_agents` (or `plate_agent`) to discover a valid agent ID.
2. Caller invokes `plate_delegate` with `agent_id`, `task`, and optional `surface`.
3. Server returns the guidance payload.
4. Caller interprets `guidance.suggested_invocation` to route the task to the correct surface or displays it to the user.

This is the primary machine-readable delegation path for orchestration agents.

#### `gh` CLI surface

1. User runs `gh plate agents list` (or `gh plate agents show <agent-id>`) to discover the agent.
2. User runs:

   ```
   gh plate delegate --agent <agent-id> "<task>"
   ```

3. The CLI calls `get_agent()` and `get_skill()` from the registry, builds the guidance payload, and prints it as formatted text (or JSON with `--json`).
4. Human-readable output example:

   ```
   Agent:    Wiki Editor (wiki-editor)
   Task:     Draft the wiki page for the baseline agents catalog.
   Surface:  gh-plate

   Persona:
     Writes and synchronizes wiki content so project state stays documented.
     Constraints: Preserve traceability back to source artifacts. Avoid inventing undocumented claims.

   Relevant Skills:
     • Document New Feature in Wiki
       Inputs:  Feature summary, Implementation notes, Source links
       Outputs: Wiki draft, Traceability notes

   Suggested invocation:
     gh plate delegate --agent wiki-editor "Draft the wiki page for the baseline agents catalog."
   ```

### Shared implementation path

All three surfaces call the same logic:

```
get_agent(agent_id)                   # registry lookup
→ build_delegation_guidance(agent, task, surface)  # pure function
→ serialize to surface format         # per-surface rendering
```

`build_delegation_guidance` is a pure function in `plate_core` that takes a `BaselineAgent`, the resolved skills, the task string, and the surface hint. It returns a plain Python dict that all three surfaces can render without re-implementing the logic.

### Phase 2 path (not in scope)

Phase 2 may introduce:

- A `PLATE_AGENT_ENDPOINT` environment variable that routes `plate_delegate` to a live agent API.
- A `status: in_progress` / `status: complete` flow with a polling ID.
- Per-surface result rendering beyond the guidance dict.

The Phase 1 `status: ready` response is forward-compatible: Phase 2 replaces it with richer status values without removing it.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Per-surface delegation logic | Inevitable drift; all three surfaces must behave identically. |
| Free-text agent name matching | Fragile; ID-based lookup is deterministic and testable. |
| Live agent invocation in Phase 1 | Out of scope and adds infrastructure risk before the core contract is stable. |
| Stateful session tracking in Phase 1 | Not needed for guidance-only responses; deferred to Phase 2. |
| Embedding task directly into the agent persona file | Persona files are static; task injection must be runtime. |

## Artifact

Implementation spans:

- `src/plate_core/baseline_catalog.py` — `get_agent()`, `get_skill()` (already present)
- `src/plate_core/mcp_server.py` — `plate_delegate` tool handler
- `src/plate_core/cli.py` — `gh plate delegate` command
- A new `build_delegation_guidance()` helper function shared by both surfaces

## Open Questions

- Should `gh plate delegate` open an interactive Copilot chat session directly, or always print guidance to stdout? Printing is the safe default for Phase 1; interactive mode deferred.
- Should the Copilot plugin surface expose `plate_delegate` as a slash command in addition to the MCP tool? Tracked as a follow-up feature.

## Acceptance Evidence

- `plate_delegate` MCP tool returns a `ready` guidance response for every valid agent in the catalog.
- `plate_delegate` returns an `error` payload for an unknown agent ID without crashing the server.
- `gh plate delegate --agent <id> "<task>"` prints formatted guidance for every valid agent.
- `gh plate delegate --agent <id> "<task>" --json` prints the same payload as `plate_delegate` MCP output.
- The `guidance.suggested_invocation` string matches the expected format for the requested surface.
- No surface delegates to a live agent process or makes external calls in Phase 1.
