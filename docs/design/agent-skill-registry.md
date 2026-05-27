# Agent and Skill Registry — Design Spec

- **Issue:** #72
- **Designed by:** Copilot / plate_core automation
- **Date:** 2026-05-28
- **Status:** Draft

## Problem

`plate_core` needs a clean registry mechanism so that agents and skills can be discovered at runtime by the Copilot plugin, MCP server, and `gh` CLI surfaces. This design specifies how definitions are loaded, the in-memory registry structure, the discovery API contract, caching and invalidation behavior, and how new agents and skills can be added without changing core code.

## Constraints

- The canonical source of truth is the YAML catalog already defined in `baseline-agents-schema.md`.
- The registry must be usable from the Copilot plugin, MCP server, and `gh` CLI without code duplication.
- Loading must fail fast and loudly if the catalog is missing or malformed.
- The design must preserve forward compatibility with future schema versions (`schema_version: 2+`).
- No external service or database is required; the registry is entirely file-backed.

## Design Decision

### 1. Catalog loading

The catalog is loaded from a single deterministic, repo-local path:

```
src/plate_core/data/baseline_catalog.yml
```

This path is resolved relative to the installed package at runtime so it works identically in development, CI, and installed deployments.

Loading steps:

1. Resolve the catalog path from `Path(__file__).resolve().parent / "data" / "baseline_catalog.yml"`.
2. Assert the file exists; raise `BaselineCatalogError` with a clear message if missing.
3. Parse with `yaml.safe_load`.
4. Validate `schema_version` is a known integer; fail for unknown versions.
5. Parse and validate `agents` and `skills` lists.
6. Enforce unique IDs within each list.
7. Enforce referential integrity: every `agent.primary_skill_ids` entry must resolve to a known skill, and every `skill.owning_agent_ids` entry must resolve to a known agent.

Custom or external catalogs may be loaded by calling the loader with an explicit path, but the baseline catalog at the package-local path is always the default.

### 2. In-memory registry structure

The registry is represented as a single frozen `BaselineCatalog` dataclass after loading:

```python
@dataclass(frozen=True)
class BaselineCatalog:
    schema_version: int
    agents: tuple[BaselineAgent, ...]
    skills: tuple[BaselineSkill, ...]
```

Each entry is a frozen dataclass:

```python
@dataclass(frozen=True)
class BaselineAgent:
    id: str
    name: str
    description: str
    primary_skill_ids: tuple[str, ...]
    constraints: tuple[str, ...]
    surfaces: tuple[str, ...]

@dataclass(frozen=True)
class BaselineSkill:
    id: str
    name: str
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    examples: tuple[str, ...]
    owning_agent_ids: tuple[str, ...]
```

Frozen dataclasses are safe to cache and share across surfaces without defensive copying.

### 3. Discovery API

The public discovery API is five pure functions exposed from `plate_core.baseline_catalog`:

| Function | Returns | Raises |
|---|---|---|
| `list_agents() -> tuple[BaselineAgent, ...]` | All agents in catalog order | `BaselineCatalogError` if catalog is invalid |
| `list_skills() -> tuple[BaselineSkill, ...]` | All skills in catalog order | `BaselineCatalogError` if catalog is invalid |
| `get_agent(agent_id: str) -> BaselineAgent` | Agent with matching `id` | `BaselineCatalogError` if not found |
| `get_skill(skill_id: str) -> BaselineSkill` | Skill with matching `id` | `BaselineCatalogError` if not found |
| `load_baseline_catalog() -> BaselineCatalog` | Full catalog | `BaselineCatalogError` if invalid |

Each surface (CLI, MCP, plugin) calls these functions and serializes the result to its own output format. No surface holds a reference to the internal catalog object beyond the current request.

Each dataclass also exposes a `to_dict() -> dict` method that returns a JSON-serializable dict suitable for CLI output and MCP payloads.

### 4. Caching and invalidation strategy

The baseline catalog is process-scoped and immutable at runtime:

- `load_baseline_catalog` is decorated with `@lru_cache(maxsize=1)`. The catalog is loaded once per process and cached in memory.
- The catalog file is read at first access; subsequent calls return the cached `BaselineCatalog`.
- To force a reload (e.g., in tests), call `load_baseline_catalog.cache_clear()`.
- No file watcher or hot-reload is required; restarts or test teardown clear the cache naturally.
- Long-running MCP servers that need to pick up catalog changes must be restarted; this is documented but not automated.

### 5. Adding agents and skills without core changes

New entries are added exclusively by editing `baseline_catalog.yml`. The loader, validator, and discovery API require no code changes when:

- A new agent is appended with a valid `id`, `name`, `description`, `primary_skill_ids` (all resolved), `surfaces`, and optional `constraints`.
- A new skill is appended with a valid `id`, `name`, `description`, `inputs`, `outputs`, `examples`, and `owning_agent_ids` (all resolved).

The only changes required for a structural catalog extension (new fields, new schema version) are:

1. Update the JSON Schema validator (planned in a follow-up feature issue).
2. Update `_load_agents` / `_load_skills` to parse the new field.
3. Bump `schema_version` in the YAML if the change is breaking.

Surface-level code does not need to change when new agents or skills are added, because all surfaces iterate the full `list_agents()` / `list_skills()` tuples.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Per-surface registries | Too easy to drift; contradicts the single-source principle. |
| Database-backed registry | Adds infrastructure complexity with no benefit for a file-backed catalog. |
| Python dataclasses as canonical source | Hard to edit without code knowledge; wedded to runtime. |
| Hot-reloading file watcher | Unnecessary complexity for a rarely-changing catalog. |
| Lazy per-lookup reads (no cache) | Causes repeated I/O on every list/get call across every request. |

## Artifact

The implementation lives in `src/plate_core/baseline_catalog.py` backed by `src/plate_core/data/baseline_catalog.yml`. No additional runtime components are required.

## Open Questions

- Should a JSON Schema file (`baseline_catalog.schema.json`) be checked in alongside the YAML so validators can be run without importing Python? Tracked as a follow-up feature.
- Should the MCP server and CLI support loading a user-supplied catalog via `--catalog` flag in addition to the baseline? Deferred to a post-Epic enhancement.

## Acceptance Evidence

- `load_baseline_catalog()` returns a populated `BaselineCatalog` for the checked-in YAML.
- An invalid `schema_version`, duplicate ID, or broken referential integrity raises `BaselineCatalogError`.
- `list_agents()`, `list_skills()`, `get_agent()`, and `get_skill()` are callable from both the CLI and MCP server without duplication.
- All 12 baseline agents and all skills are present and valid in the returned catalog.
- Calling `load_baseline_catalog()` twice in the same process returns the same object (cache hit).
