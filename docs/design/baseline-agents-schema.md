# Baseline Agents and Skills — Schema Contract

- **Issue:** #71
- **Designed by:** Copilot / plate_core automation
- **Date:** 2026-05-27
- **Status:** Draft

## Problem

plate_core needs a durable v1 schema for the baseline agent and skill catalog so the 12 planned agents can be loaded, validated, and exposed consistently across CLI, MCP, and plugin surfaces.

## Constraints

- The schema must align with the current YAML-based registry style already used in `.agentic/`.
- The source of truth should not live in Python code.
- Validation must be machine-enforced, not just implied by docs.
- The catalog must remain easy to render into `.agent.md` persona files and CLI/MCP JSON output.

## Design Decision

### Canonical format

Use a versioned **YAML catalog** as the canonical source of truth, with **JSON Schema** as the validation contract.

Recommended catalog split:

- `agents` catalog for baseline agent personas
- `skills` catalog for reusable capability definitions
- schema files versioned with the catalog shape

### Minimal v1 agent shape

```yaml
schema_version: 1
agents:
  - id: plate
    name: PLATE Core Agent
    description: Context-first coordinator for PLATE repos and epics.
    primary_skill_ids:
      - repo-health
      - epic-triage
    surfaces:
      - copilot-plugin
      - gh-plate
      - mcp
    constraints:
      - Keep responses concise and action-oriented.
      - Do not claim live state without querying the repo.
```

### Minimal v1 skill shape

```yaml
schema_version: 1
skills:
  - id: repo-health
    name: Repository health triage
    description: Summarize labels, branch protection, and epic status.
    artifacts:
      - CURRENT.md
      - docs/research/
    surfaces:
      - copilot-plugin
      - gh-plate
```

### Validation strategy

1. Load the catalog from a deterministic repo-local path.
2. Validate file structure and required keys against JSON Schema.
3. Enforce unique IDs within each catalog.
4. Enforce referential integrity between agents and skills.
5. Fail fast if a required catalog file is missing or malformed.

### Versioning strategy

- Keep the schema explicitly versioned with `schema_version`.
- Treat incompatible field changes as a new schema version, not as silent drift.
- Preserve the v1 contract until there is a deliberate migration path.

## Alternatives Rejected

| Alternative | Why Rejected |
|---|---|
| Python dataclasses as the source of truth | Too coupled to runtime code and awkward for non-code editing. |
| Markdown-only catalog | Hard to validate consistently and too loose for cross-surface reuse. |
| Ad hoc JSON files without schema | Easy to parse, but too brittle without a clear contract. |

## Artifact

The implementation should add a repo-local catalog directory with schema-validated YAML definitions that can be rendered into agent prompts and registry output.

## Acceptance Evidence

- The catalog loads successfully from the repo.
- Invalid schema versions or missing fields fail tests.
- Every baseline agent resolves to at least one valid skill.
- The catalog can be serialized into both CLI JSON and plugin-facing agent files.
