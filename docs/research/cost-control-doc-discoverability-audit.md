# Cost Control Audit of Prompt Duplication and Documentation Discoverability

- **Issue:** #393
- **Researched by:** @copilot
- **Date:** 2026-06-08
- **Status:** Completed

## Research Question

How should PLATE reorganize agent-facing documentation so the authoritative answer is easier to find on GitHub and in-repo without forcing the agent to scan many overlapping files?

## Sources

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `plugin/agents/plate.agent.md`
- `.agentic/skills.yml`
- `src/plate_core/data/baseline_catalog.yml`
- `docs/research/copilot-cli-friendly-agent-skill-definitions.md`
- `docs/research/mcp-agent-skill-exposure-patterns.md`
- `docs/design/agent-skill-registry-and-discovery.md`
- `docs/design/mcp-agent-skill-tool-surface.md`
- `docs/design/single-agent-delegation-flow.md`
- Recent GitHub Copilot CLI session history for `akasper/plate` queried on 2026-06-08 (last 14 days, repository-scoped)

## Findings

### 1. PLATE has an authority hierarchy, but not a clear discovery hierarchy

The repository already has durable truth sources for different concerns:

- `AGENTS.md` for operating rules and ceremonies
- `SPEC.md` for intended future state
- `.agentic/releases/` for change memory
- `baseline_catalog.yml` for agent/skill metadata
- `plugin/agents/plate.agent.md` and `.github/copilot-instructions.md` for surface-specific behavior

The problem is not a lack of authoritative artifacts. The problem is that agents still have to infer **which artifact to read first** for a given question. That discoverability burden currently sits in scattered prose rather than in one obvious index.

### 2. Navigation guidance is duplicated across multiple entrypoint surfaces

The same kinds of instructions appear in several places:

| Concern | Current surfaces |
|---|---|
| Source-of-truth / durability rules | `AGENTS.md`, `.github/copilot-instructions.md` |
| Workflow and "what to check next" guidance | `plugin/agents/plate.agent.md`, `src/plate_core/agent_guidance.py`, `AGENTS.md` |
| Agent/skill discovery guidance | `plugin/agents/plate.agent.md`, `docs/design/agent-skill-registry-and-discovery.md`, `docs/research/copilot-cli-friendly-agent-skill-definitions.md` |
| Delegation guidance | `plugin/agents/plate.agent.md`, `docs/design/single-agent-delegation-flow.md`, `docs/design/mcp-agent-skill-tool-surface.md` |

This means the agent can rarely answer "where should I look?" from a single surface. Instead it often reads several large files that each mix durable policy with navigation hints.

### 3. Session history shows a real discoverability tax

Across recent `akasper/plate` Copilot CLI sessions, the most common named read/search targets were:

| Target group | Calls |
|---|---:|
| `AGENTS.md` | 84 |
| `docs/design/*` | 48 |
| `docs/research/*` | 31 |
| `plugin/agents/plate.agent.md` | 24 |
| `SPEC.md` | 20 |
| `.github/copilot-instructions.md` | 9 |
| `.agentic/skills.yml` | 5 |

This is an information-architecture smell. Important guidance is discoverable, but only by hopping between policy docs, surface prompts, and deep design/research artifacts. The amount of reading is a signal that entrypoint docs do not yet narrow the search space enough.

### 4. The machine-readable discovery surfaces are better than the prose entrypoints

PLATE already has a cleaner discovery pattern in code than in prose:

- `docs/design/agent-skill-registry-and-discovery.md` defines stable `list_agents()`, `get_agent()`, `list_skills()`, and `get_skill()` APIs.
- `docs/research/mcp-agent-skill-exposure-patterns.md` recommends catalog-driven metadata and keeping `.agent.md` files thin.
- `docs/design/mcp-agent-skill-tool-surface.md` standardizes discoverable `plate_*` tools and "Call this when..." descriptions.

In other words, the repository already contains the ingredients for low-friction discovery, but the entrypoint documents still behave like broad narrative prompts rather than thin routers into those machine-readable surfaces.

### 5. GitHub-native and in-repo discoverability are not yet unified

PLATE has several discoverability channels:

- GitHub issue labels, milestones, and templates
- `gh plate` subcommands such as `agents list/show` and release-status surfaces
- MCP tools such as `plate_agents`, `plate_agent`, `plate_skills`, and `plate_delegate_to_agent`
- In-repo docs under `docs/research/` and `docs/design/`

These channels are individually useful, but they are not presented as a single coherent map. An agent can find the answer, but it first has to decide whether the answer probably lives in GitHub issue state, catalog metadata, a design doc, a research doc, or a top-level instruction file.

### 6. The highest-value duplication to remove is "navigation duplication," not all duplication

Not all repetition is bad. Some repetition is appropriate because different surfaces need local instructions. The expensive duplication is the repeated explanation of:

1. which source of truth matters for which question,
2. which command or tool should be used to discover that truth, and
3. which deeper artifact to open next.

That is the part that should become canonical.

## Recommendation

Adopt a **layered discoverability architecture** for Epic #391:

### A. Define one canonical context/discovery index

Create a single canonical artifact or generated surface whose only job is to answer:

- Where does authoritative truth live for policy, product intent, runtime metadata, and workflow state?
- Which CLI/MCP surfaces expose that truth directly?
- Which deep docs are background/reference docs rather than default entrypoints?

This index should be usable both by humans and by agents.

### B. Keep entrypoint prompts thin and pointer-oriented

Reduce `plugin/agents/plate.agent.md` and host-agent instructions so they mostly:

- establish behavior for the current surface,
- point to the canonical discovery/index surface,
- name the small set of tools/commands to use first,
- avoid re-explaining large sections of PLATE policy already owned by `AGENTS.md`.

### C. Separate policy from retrieval guidance

Use:

- `AGENTS.md` for durable operating rules,
- the canonical index for "where to look next",
- machine-readable catalog/tool surfaces for agent/skill discovery,
- design/research docs as reference material rather than default starting points.

### D. Prefer machine-readable discovery before prose search

When the answer can be found from catalog/tool/index surfaces, agents should not need to read multiple Markdown files first. That means future implementation work should expose more "what should I read/use next?" guidance through stable CLI/MCP outputs instead of only prose.

### E. Treat deep docs as linked references, not stacked prompts

`docs/design/*` and `docs/research/*` should remain durable references, but entrypoint surfaces should link to the relevant document instead of embedding their contents or forcing broad doc scans.

## Recommended Follow-up Sequencing

1. **#394** should define the layered context/discovery architecture and the canonical index shape.
2. **#395** should define how delegation packets reference that discovery architecture without copying it.
3. **#396** should slim the entrypoint docs/prompts after the architecture is agreed.
4. **#397** should implement the canonical discovery surfaces.
5. **#398** should align delegation with the new discovery model.

In short: the documentation problem is not that PLATE has too much truth, but that it lacks a **single obvious front door** to that truth.
