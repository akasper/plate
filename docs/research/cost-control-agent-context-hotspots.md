# Cost Control Hotspots for Agent Context and Tool Calls

- **Issue:** #392
- **Researched by:** @copilot
- **Date:** 2026-06-08
- **Status:** Completed

## Research Question

Where are PLATE agent sessions currently spending the most prompt/context budget and exploratory tool calls across agent-facing documents, skills, and delegation flows?

## Sources

- `AGENTS.md`
- `SPEC.md`
- `.github/copilot-instructions.md`
- `plugin/agents/plate.agent.md`
- `.agentic/skills.yml`
- `.github/agents/plate-configurator.agent.md`
- `src/plate_core/agent_guidance.py`
- `src/plate_core/data/baseline_catalog.yml`
- `docs/research/copilot-cli-friendly-agent-skill-definitions.md`
- `docs/research/mcp-agent-skill-exposure-patterns.md`
- `docs/design/mcp-agent-skill-tool-surface.md`
- `docs/design/single-agent-delegation-flow.md`
- Recent GitHub Copilot CLI session history for `akasper/plate` queried on 2026-06-08 (last 14 days, repository-scoped)
- Local file-size measurements captured on 2026-06-08

## Findings

### 1. The largest cost hotspot is the entrypoint instruction layer, not the skill registry

The biggest agent-facing artifacts are concentrated in a small set of top-level instruction files:

| Artifact | Size | Why it matters |
|---|---:|---|
| `AGENTS.md` | 39,678 bytes / 453 lines | Global operating doctrine; often needed for process-sensitive work |
| `src/plate_core/data/baseline_catalog.yml` | 23,187 bytes / 687 lines | Central catalog, but not a human-friendly entrypoint |
| `SPEC.md` | 19,108 bytes / 185 lines | Product intent and roadmap source of truth |
| `src/plate_core/agent_guidance.py` | 8,933 bytes / 147 lines | Embedded reusable guidance blocks |
| `.github/copilot-instructions.md` | 7,987 bytes / 74 lines | Host-agent instruction layer |
| `plugin/agents/plate.agent.md` | 5,695 bytes / 46 lines | PLATE agent entrypoint prompt |
| `.agentic/skills.yml` | 4,368 bytes / 118 lines | Skill policy surface |

This means the dominant context problem is not "too many tiny files"; it is that PLATE keeps several large, partially overlapping entrypoint layers that each look important enough to read before acting.

### 2. Live-state discovery dominates exploratory tool use

Recent `akasper/plate` Copilot CLI session history shows that the most common tool calls are:

| Tool | Calls |
|---|---:|
| `bash` | 826 |
| `view` | 711 |
| `report_intent` | 472 |
| `apply_patch` | 206 |
| `sql` | 146 |
| `rg` | 123 |

For sessions with captured tool-request history, the average recorded session used **337.4 tool calls**, with a maximum of **1,284**. This indicates that cost is strongly driven by repeated state acquisition and navigation, not just final implementation work.

Inside `bash`, the most common exploratory command groups were:

| Command group | Calls |
|---|---:|
| `gh issue view` | 73 |
| `git status` | 64 |
| `gh issue list` | 27 |
| `gh pr list` | 24 |
| `gh plate release status` | 9 |

The pattern is consistent: agents repeatedly spend budget rediscovering issue state, PR state, repo cleanliness, and release targeting before they can begin the actual task.

### 3. A few files absorb a disproportionate share of reads

Among `view` calls in recent repository sessions, the most frequently targeted named artifacts were:

| Target | Calls |
|---|---:|
| `AGENTS.md` | 36 |
| `plugin/agents/plate.agent.md` | 13 |
| `SPEC.md` | 6 |
| `.agentic/skills.yml` | 4 |
| `.github/copilot-instructions.md` | 4 |

`AGENTS.md` is the clear read hotspot. That is not surprising: it contains critical process rules, but it also means PLATE currently places too much "must know before acting" information into a single heavyweight artifact.

### 4. The current architecture duplicates "where to look next" guidance across several surfaces

Multiple files tell the agent how to navigate the repository:

- `plugin/agents/plate.agent.md` instructs the PLATE agent to gather health, epic, features, and delegation context before acting.
- `.github/copilot-instructions.md` tells the host agent to treat repository artifacts as durable truth and keep `AGENTS.md`, process config, and implementation aligned.
- `AGENTS.md` adds the resource-consciousness rule and the full issue/PR/release ceremonies.
- Research and design docs describe "thin `.agent.md`", catalog-driven metadata, and "Call this when..." routing patterns.

These pieces are individually reasonable, but together they create a stacked-entrypoint problem: several artifacts re-explain navigation and authority instead of providing one canonical discovery layer plus thinner surface-specific pointers.

### 5. Delegation is still prompt-heavy even though PLATE already has the right conceptual model

PLATE's prior research/design direction already points at the lower-cost answer:

- `docs/research/mcp-agent-skill-exposure-patterns.md` recommends keeping `.agent.md` files thin and making the catalog authoritative.
- `docs/design/mcp-agent-skill-tool-surface.md` standardizes "Call this when..." descriptions so the model can route without extra explanation.
- `docs/design/single-agent-delegation-flow.md` defines delegation as routing-by-metadata, not subprocess execution.

The gap is implementation emphasis. The design direction is already compatible with cheaper delegation, but the current repo still exposes large upstream context surfaces that encourage broad prompt assembly and repeated re-reading.

### 6. The main cost centers are therefore architectural, not purely editorial

The hotspot pattern can be summarized as:

1. **Large entrypoint docs** create expensive default context.
2. **Overlapping discovery guidance** forces repeated reading of multiple sources of "what to check next".
3. **Live GitHub state checks** consume many bash calls before work can start.
4. **Delegation handoffs** still inherit too much broad context instead of a small, typed task packet.

This means trimming wording alone will not deliver the full win. PLATE needs a smaller context architecture and clearer canonical discovery surfaces.

## Recommendation

Prioritize the rest of Epic #391 in this order:

1. **Design a layered context architecture first** (`#394`): define a small set of thin entrypoint surfaces and explicit canonical retrieval targets.
2. **Design narrow delegation packets second** (`#395`): delegation should pass only scoped task context, artifact links, and retrieval hints.
3. **Implement the slim-down of agent-facing docs and prompts** (`#396`) after the architecture is agreed, rather than trimming files ad hoc.
4. **Add canonical discovery/index surfaces** (`#397`) so fewer `gh issue view`, `gh issue list`, and repeated doc reads are needed to find repository truth.
5. **Implement short delegation packets and routing hints** (`#398`) so sub-agents start from narrower prompts by default.

In short: the highest-leverage cost-control opportunity is to replace PLATE's current stacked instruction layers with a **thin-entrypoint + canonical-discovery + narrow-delegation** model.
