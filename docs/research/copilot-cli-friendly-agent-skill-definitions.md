# Requirements for Making Agent and Skill Definitions Friendly to GitHub Copilot CLI Plugins

- **Issue:** #70
- **Researched by:** @copilot (agent session)
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

What does it mean in practice for agent and skill definitions to be "friendly to GitHub Copilot CLI plugins"?
Specifically: how does Copilot consume context and tools, what formats and metadata aid discoverability and
invocation, what common pitfalls exist, and what naming/schema/example conventions work best?

## Sources

- [Custom agents configuration — docs.github.com](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [About custom agents for Copilot — docs.github.com](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-custom-agents)
- [MCP specification — modelcontextprotocol.io](https://modelcontextprotocol.io/specification)
- `docs/research/custom-agent-packaging.md`
- `docs/research/mcp-agent-skill-exposure-patterns.md`
- `plugin/agents/plate.agent.md`
- `src/plate_core/data/baseline_catalog.yml`
- `src/plate_core/mcp_server.py`

## Findings

### 1. How Copilot CLI Plugins Consume Context and Tools

The Copilot CLI plugin system works in two layers:

#### Layer 1: Agent Persona (`.agent.md`)

The `.agent.md` file defines **who the agent is** and **what it should do**. The LLM reads this as a system
prompt. Key frontmatter fields consumed by Copilot:

| Field | How Copilot Uses It |
|---|---|
| `name` | Shown in the agent picker; used for `@name` invocation |
| `description` | Shown as subtitle in the agent picker; drives user intent matching |
| `tools` | List of MCP tool names the agent is allowed to call |
| `model` | Optional model override; defaults to user's configured Copilot model |

**Critical insight:** The `description` field is the *primary* discovery signal. Copilot shows it in the
agent picker and uses it for semantic matching when a user searches for an agent. A bad description = invisible agent.

#### Layer 2: MCP Tool Invocation

When an agent calls a tool, Copilot routes the call to the MCP server identified in `.mcp.json`.
The LLM decides *which tool to call* based on the tool's `description` and `inputSchema`. It does not
have prior knowledge of what tools exist — it learns from `tools/list` at session start.

**Critical insight:** Tool descriptions must tell the LLM **when** to call them, not just **what** they do.
- ❌ Bad: `"Return agent list."`
- ✅ Good: `"Return the full list of baseline plate agents. Call this when the user asks what agents are available, which agent to use, or wants an overview of plate capabilities."`

### 2. What Makes Definitions Copilot-Friendly

#### Agent `.agent.md` Friendliness

| Property | Friendly Pattern | Anti-Pattern |
|---|---|---|
| `name` | Short, pronounceable, memorable (`plate`, `market-researcher`) | Long compound words (`plate_core_agent_v2`) |
| `description` | Action-oriented, 1-2 sentences, answers "what does this agent help me do?" | Internal jargon, version numbers, vague ("AI assistant") |
| Instructions body | Numbered workflow, explicit tool call cues, behavioral rules | Prose paragraphs without clear action steps |
| Tool references | Match MCP tool `name` exactly | Invented names not in the MCP server |

#### MCP Tool Friendliness

| Property | Friendly Pattern | Anti-Pattern |
|---|---|---|
| Tool `name` | Verb-noun or domain-prefix underscore form | CamelCase, hyphens, ambiguous abbreviations |
| Tool `description` | "Call this when…" framing; lists common user intents | Technical implementation detail only |
| `inputSchema` | Mark truly required params with `"required":[...]`; include `description` on each property | Flat schema with no property descriptions |
| Error responses | Use `isError: true` with a human-readable message string | Bare exceptions or empty content |

#### Skill Definition Friendliness

For plate_core's YAML catalog, a Copilot-friendly skill definition:

- Has a `description` that answers "what user goal does this skill serve?"
- Lists `inputs` and `outputs` in terms of observable artifacts, not internal field names
- Includes at least one `example` that reads like a real user request
- Has `owning_agent_ids` populated so the router can suggest the right agent

Example of a Copilot-friendly skill entry:

```yaml
- id: repo-health
  name: Repository health triage
  description: >
    Summarizes label coverage, branch protection status, and open epic counts
    for a PLATE repository. Use this when a user asks "is my repo healthy?" or
    "what's broken in my PLATE setup?"
  inputs:
    - "owner/repo identifier (optional if running inside repo)"
  outputs:
    - "status: pass | warn | fail"
    - "missing labels list"
    - "branch protection enabled flag"
    - "open epic count"
  examples:
    - "Check health of akasper/plate"
    - "Is my repo set up correctly?"
  owning_agent_ids:
    - plate
```

### 3. Common Pitfalls

| Pitfall | Impact | Mitigation |
|---|---|---|
| Vague tool descriptions | LLM skips the tool or hallucinates a different invocation | Rewrite with "Call this when…" framing |
| Missing `required` in `inputSchema` | LLM passes incomplete args; server errors are confusing | Mark all non-optional fields as `required` |
| Tool names that shadow built-ins | Unexpected routing to wrong tool | Use `plate_` prefix for all domain tools |
| Agent instructions without explicit tool cues | Agent doesn't know when to call MCP tools | Add "Call MCP tool X when…" lines to instructions |
| Skill definitions with no examples | Agent can't match user intent to skill | Add ≥1 natural-language example per skill |
| Agent `.agent.md` describes implementation, not behavior | Developer-readable but user-hostile | Rewrite agent instructions from the user's POV |
| Overly broad `tools` list in agent frontmatter | LLM gets confused by too many choices | Keep tool list to the minimum needed per agent |

### 4. Recommendations for plate_core

#### Naming

- **Agent IDs:** kebab-case, human-readable nouns (`project-manager`, `research-agent`). These map
  cleanly to Copilot `@agent-name` invocations and `gh plate agents show <id>`.
- **Skill IDs:** kebab-case verb-noun (`crud-projects`, `groom-backlog`). Mirrors the user action.
- **MCP tool names:** `plate_` prefix + snake_case verb-noun (`plate_agents`, `plate_delegate_to_agent`).

#### Description Quality

- Every agent `description` should pass the "picker test": if a user sees only this sentence in the
  agent picker, would they know whether to select it?
- Every MCP tool `description` should pass the "LLM routing test": given only this text, would a
  language model know when to call this tool vs. another?
- Every skill `description` should answer "what user problem does this solve?"

#### Schema and Validation

- The `baseline_catalog.yml` YAML schema provides the source of truth. Enforce it at load time
  (as `plate_core.baseline_catalog` already does) so bad definitions fail fast, not silently.
- Required fields: `id`, `name`, `description`, `surfaces` (agents), `owning_agent_ids` (skills).
- Optional but strongly recommended: `examples`, `constraints`, `inputs`, `outputs`.

#### Plugin Wiring Checklist

For a new agent or skill to be fully Copilot-friendly:

- [ ] Entry in `baseline_catalog.yml` with description + examples
- [ ] Corresponding `.agent.md` in `plugin/agents/` with correct `tools` list
- [ ] MCP tool(s) referenced by the agent are registered in `mcp_server.py` `tools/list`
- [ ] `plate_features` detection includes the new capability path
- [ ] At least one test asserts the catalog entry loads correctly

## Recommendation

The plate_core catalog and plugin surface already follow the right patterns (kebab IDs, structured YAML,
MCP tool prefix). The remaining gap is **description quality**: agent instructions and skill examples need
the "Call this when…" and "user request: …" framing to perform well with LLM routing.

As the catalog grows, add a lint step (`scripts/validate_catalog.py` or CI check) that enforces:
- non-empty descriptions on all catalog entries
- at least one example per skill
- every agent surfaces list is non-empty
- MCP tool names declared in `.agent.md` exist in `mcp_server.py`

### Follow-up Actions

- Add example-quality validation to CI: add to `tests/test_baseline_catalog.py`
- Design the delegation tool surface with "Call this when…" framing: Issue #74
- Review and improve description quality across all 12 baseline agents once delegation is implemented
