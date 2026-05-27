# Agent and Skill Registry and Discovery System — Design Spec

- **Issue:** #72
- **Designed by:** @copilot (agent session)
- **Date:** 2026-05-27
- **Status:** Approved (implemented in PR #85)

## Problem

plate_core needs a clean registry mechanism so that agents and skills can be discovered at runtime by
the Copilot plugin, MCP server, and `gh plate` CLI surfaces — without requiring consumers to parse raw
YAML or understand internal data structures.

## Constraints

- The source of truth must remain in a human-editable, diff-friendly format (YAML).
- The registry must be safe to call from concurrent MCP requests (immutable after load).
- Adding new agents or skills must not require changes to the core module — only to the catalog YAML.
- Discovery APIs must return the same entity shapes regardless of which surface calls them.
- The registry must fail loudly on malformed input rather than silently returning partial data.

## Design Decision

### Catalog Location and Format

The canonical catalog lives at `src/plate_core/data/baseline_catalog.yml` and follows the schema defined
in `docs/design/baseline-agents-schema.md`. It is version-pinned (`schema_version: 1`) and validated
at load time.

### Load and Validation Strategy

```
baseline_catalog.yml
        │
        ▼
  _load_yaml()         ← reads YAML, asserts it is a dict
        │
        ▼
  _load_agents()       ← validates ids, types, surfaces, skill refs
  _load_skills()       ← validates ids, types, owning_agent refs
        │
        ▼
  BaselineCatalog      ← frozen dataclass; referential integrity verified
        │
        ▼
  lru_cache(maxsize=1) ← single in-process load; safe for concurrent reads
```

The `lru_cache` ensures the catalog is loaded exactly once per process, making it safe to call
from concurrent MCP stdio reads or multiple CLI invocations without file I/O on every request.

### Registry Structure

The in-memory registry is the `BaselineCatalog` frozen dataclass:

```python
@dataclass(frozen=True)
class BaselineCatalog:
    schema_version: int
    agents: tuple[BaselineAgent, ...]
    skills: tuple[BaselineSkill, ...]

    def agent_by_id(self, agent_id: str) -> BaselineAgent: ...
    def skill_by_id(self, skill_id: str) -> BaselineSkill: ...
```

All entities are frozen (immutable), preventing accidental mutation by any consumer.

### Discovery APIs

The public module API exposes four functions:

| Function | Returns | Used By |
|---|---|---|
| `list_agents()` | `tuple[BaselineAgent, ...]` | CLI `agents list`, MCP `plate_agents` |
| `get_agent(agent_id)` | `BaselineAgent` | CLI `agents show`, MCP `plate_agent` |
| `list_skills()` | `tuple[BaselineSkill, ...]` | CLI `skills list`, MCP `plate_skills` |
| `get_skill(skill_id)` | `BaselineSkill` | CLI `skills show`, MCP `plate_skill` |

Each entity has a `.to_dict()` method that produces a stable, JSON-serializable representation.
Surfaces call `.to_dict()` rather than accessing dataclass fields directly, ensuring the wire format
does not change if internal fields are renamed.

### Caching and Invalidation

- The `lru_cache` caches the catalog for the lifetime of the process.
- Tests that modify catalog behavior must call `load_baseline_catalog.cache_clear()` before and after.
- No runtime invalidation is needed: the catalog is static content shipped with the package.
- Future support for user-supplied catalog overlays would require a separate invalidation mechanism
  (out of scope for v1).

### Extensibility: Adding New Agents/Skills

To add a new agent without changing core module code:

1. Add an entry to `src/plate_core/data/baseline_catalog.yml` following the v1 schema.
2. Add or update the corresponding `.agent.md` in `plugin/agents/`.
3. Run tests — the catalog loader validates the entry automatically.

No Python changes are required unless the new agent needs a new *surface* (MCP tool, CLI subcommand).

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Python dicts as the registry | No schema enforcement; easy to introduce drift |
| SQLite or in-memory DB | Too heavy for a static catalog read at startup |
| Re-reading YAML on every request | Unnecessary I/O; all clients would see inconsistent state during writes |
| Separate registries per surface | Drift is guaranteed; one catalog serves all surfaces by design |

## Artifact

Implemented in:
- `src/plate_core/baseline_catalog.py` — loader, models, public API
- `src/plate_core/data/baseline_catalog.yml` — catalog data (12 agents, 18+ skills)
- `tests/test_baseline_catalog.py` — load, reference integrity, schema version tests

## Open Questions

None for v1. Potential future work:
- User-supplied catalog overlays for custom agents not in the baseline
- Schema version migration when v2 shape is needed

## Acceptance Evidence

- `load_baseline_catalog()` returns 12 agents and ≥18 skills.
- All agent `primary_skill_ids` resolve to valid skills in the same catalog.
- All skill `owning_agent_ids` resolve to valid agents.
- Invalid `schema_version` raises `BaselineCatalogError`.
- `list_agents()`, `get_agent()`, `list_skills()`, `get_skill()` all covered by tests.
