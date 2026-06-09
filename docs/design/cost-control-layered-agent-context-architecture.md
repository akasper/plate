# Layered Agent Context Architecture for Lean Prompts — Design Spec

- **Issue:** #394
- **Designed by:** @copilot
- **Date:** 2026-06-08
- **Status:** Draft

## Problem

PLATE currently has strong durable truth artifacts, but weak default wayfinding between them. Agents often need to read `AGENTS.md`, host-agent instructions, the PLATE agent prompt, and deep design/research docs before they can answer a basic question such as:

- what source of truth applies,
- what tool or command should be called first, or
- which deeper artifact should be opened next.

That stacked-entrypoint model raises prompt cost, increases exploratory tool calls, and makes delegation heavier than necessary.

## Constraints

- Preserve PLATE's source-of-truth model: `AGENTS.md`, `SPEC.md`, `.agentic/releases/`, runtime catalog metadata, and GitHub issue state each keep their current authority boundaries.
- Do not solve this by deleting durable reference material; solve it by changing the retrieval path.
- Work across all relevant surfaces: repository-scoped agents, host-agent instructions, `gh plate`, MCP, and GitHub-native issue/PR navigation.
- Keep the resulting architecture explainable to humans, not only machine-optimized.
- Allow machine-readable discovery to become the preferred default without breaking existing prose docs.

## Design Decision

Adopt a **five-layer context architecture** with a single canonical discovery layer in front of the existing durable truth artifacts.

### Layer 0: Live state

This layer answers questions whose truth comes from current repository or GitHub state.

Examples:
- open issues / PRs / milestones
- release targeting
- health and feature detection
- agent/skill inventory returned from runtime surfaces

Primary surfaces:
- `gh issue/pr/...`
- `gh plate ...`
- MCP tools such as `plate_health`, `plate_epic_status`, `plate_agents`, `plate_skill`, `plate_delegate_to_agent`

### Layer 1: Canonical context map (new)

This is the missing front door. It does **not** replace existing truth sources. It tells the agent:

1. what kind of question it is answering,
2. which surface to query first,
3. which artifact is authoritative for the answer, and
4. which background references are optional.

This layer should become the first place an agent consults for "where do I look?" rather than forcing the agent to infer the path from multiple prompts.

#### Proposed shape

Represent the layer as one logical model that can be rendered into multiple surfaces:

```json
{
  "concern": "release-targeting",
  "first_step": "Run gh plate release status",
  "authoritative_artifacts": [
    "AGENTS.md §Branch Model and Ceremonies",
    ".agentic/releases/"
  ],
  "machine_surfaces": [
    "gh plate release status",
    "plate_release_status"
  ],
  "reference_docs": [
    "docs/design/release-ceremony-refinement.md"
  ]
}
```

The important design constraint is **single logical source, multiple renderings**:

- human-readable Markdown index
- CLI/MCP query surface
- surface-specific pointers from prompts and instructions

### Layer 2: Surface entrypoints

These are the files or prompts an agent sees first in a given environment:

- `plugin/agents/plate.agent.md`
- `.github/copilot-instructions.md`
- `.github/agents/*.agent.md`

Under the new design, these surfaces should be **thin routers**, not broad narrative bundles.

Their responsibilities:

1. establish behavior specific to the current surface,
2. point to the canonical context map,
3. name the small set of first tools/commands to use,
4. state only the minimum local rules that cannot be delegated elsewhere.

Their non-responsibilities:

1. re-explaining major sections of `AGENTS.md`,
2. embedding large blocks of reference material,
3. repeating discovery guidance already present in the canonical context map.

### Layer 3: Durable authority artifacts

This layer remains authoritative for its current domains:

| Artifact | Authority |
|---|---|
| `AGENTS.md` | operating doctrine, work loops, ceremonies, escalation, merge policy |
| `SPEC.md` | intended product / process goal state |
| `.agentic/releases/` | change memory and release migration truth |
| `baseline_catalog.yml` and derived APIs | agent/skill metadata |
| GitHub issues / milestones / labels / PR state | live planning and execution state |

The design does **not** collapse these into one file. It standardizes how the agent reaches them.

### Layer 4: Reference material

This layer includes:

- `docs/design/*`
- `docs/research/*`
- other deep reference docs

These remain important, but they should no longer function as default entrypoints. They are linked references used when the context map or authority layer says deeper background is needed.

## Routing rules

The layered architecture uses these rules:

1. **Start from the context map when the task is "where do I look?"**
2. **Use live-state surfaces before prose when the answer is dynamic.**
3. **Use durable authority artifacts before reference docs when the answer is normative.**
4. **Use reference docs only when background, rationale, or prior tradeoffs are needed.**
5. **Entry-point prompts should link downward, not copy upward.**

## Prompt-budget policy

This design introduces a soft prompt-budget discipline:

- Entry-point surfaces should contain only local behavior plus routing guidance.
- Anything that is primarily reference material should be moved behind the canonical context map or a direct tool/command.
- Duplication is acceptable only when it improves local surface usability and does not recreate a second discovery system.

This is intentionally a policy direction rather than a hard byte-count gate. The follow-up Features should decide whether specific size thresholds are useful once the index model exists.

## Recommended implementation shape for follow-up Features

### For #396 (slim docs/prompts)

- Reduce entrypoint docs to surface-specific rules plus links/pointers.
- Move general "what to consult next" logic out of broad prompts.
- Keep `AGENTS.md` as doctrine, not as the only practical discovery path.

### For #397 (canonical discovery surfaces)

Implement the context map as at least two renderings:

1. a human-readable repository artifact, and
2. a machine-readable CLI/MCP surface.

That enables agents to retrieve discovery guidance directly instead of scanning prose.

### For #398 (delegation)

Delegation packets should reference the context map by scoped concern instead of copying large rule blocks into each handoff.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Keep current documents and only trim wording | Reduces bytes but leaves the same discoverability problem |
| Collapse all truth into one giant master instruction file | Maximizes discoverability at the cost of prompt size, maintenance burden, and authority clarity |
| Make design/research docs the primary entrypoint | Deep docs are useful references, but too heavy and too broad for default routing |
| Use only machine-readable outputs and stop maintaining prose docs | Humans still need inspectable architecture and rationale; PLATE is human-owned and agent-assisted |
| Keep separate discovery guidance inside each prompt surface | Recreates the duplication problem and guarantees drift |

## Artifact

### Proposed concern-to-surface flow

| Concern | First surface | Authority | References |
|---|---|---|---|
| process / ceremony | context map → `AGENTS.md` | `AGENTS.md` | relevant design docs |
| product / goal state | context map → `SPEC.md` | `SPEC.md` | research/design background |
| agent / skill lookup | context map → CLI/MCP list/show | catalog metadata | design docs |
| release targeting | context map → `gh plate release status` | live GitHub + `AGENTS.md` | release ceremony design |
| delegation | context map → delegation surface | catalog + packet schema | delegation design |

### ASCII architecture

```text
Surface prompt / host instructions
            |
            v
   Canonical context map
            |
    ---------------------
    |         |         |
    v         v         v
 live state  authority  references
 surfaces     docs       docs
```

## Open Questions

- Should the canonical context map live as generated data, hand-authored data, or a hybrid?
- Should the human-readable index be in `docs/`, repository root, wiki source, or all three via generation?
- How much of the context map should be repository-generic versus repo-specific?

## Acceptance Evidence

This design is implemented correctly when follow-up work delivers all of the following:

1. Agents can answer "where should I look first?" from one canonical discovery surface.
2. Entry-point prompts become materially smaller without losing essential routing quality.
3. The authoritative artifact for a concern is explicit rather than inferred.
4. Agents can prefer machine-readable discovery before broad prose scans.
5. Delegation packets can point to scoped discovery guidance instead of carrying large prompt bundles.
