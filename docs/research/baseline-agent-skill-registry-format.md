# Baseline Agent and Skill Registry Format

- **Issue:** #66, #69
- **Researched by:** Copilot / plate_core automation
- **Date:** 2026-05-27
- **Status:** Completed

## Research Question

What is the most sustainable format for defining the 12 baseline agents and their skills? Evaluate YAML / Markdown frontmatter, Python dataclasses, JSON Schema, and hybrid approaches for readability, validation, versioning, and exposure through plate_core surfaces.

## Sources

- `AGENTS.md`
- `.agentic/extensions.yml`
- `.agentic/skills.yml`
- `.github/agents/plate-configurator.agent.md`
- `docs/research/custom-agent-packaging.md`
- `docs/research/stack-selection.md`
- `docs/migration/baseline.md`
- `README.md`
- `SPEC.md`
- `CURRENT.md`

## Findings

### Current shape in the repo

The repository already uses a hybrid, but it is not yet a canonical catalog:

- `.agentic/extensions.yml` describes optional PLATE extensions and their artifacts.
- `.agentic/skills.yml` describes skill profiles and allowed artifacts.
- `.github/agents/*.agent.md` is the Copilot-native surface for conversational agents.
- `docs/research/custom-agent-packaging.md` already recommends native `.agent.md` agent files plus registry entries.

This means the repository has the ingredients for a baseline catalog already; the missing piece is a single, versioned source of truth with validation.

### Option comparison

| Option | Strengths | Weaknesses |
|---|---|---|
| YAML | Human-editable, diff-friendly, easy to generate docs from, matches current registry files | Needs schema validation to avoid drift |
| Markdown frontmatter | Natural for agent personas and Copilot-native instruction files | Harder to validate nested catalog data consistently |
| Python dataclasses | Easy to load inside runtime code | Bad source-of-truth for non-developers and awkward for surface generation |
| JSON Schema | Strong validation and versioning | Poor authoring experience by itself |

### Recommendation

Use a **YAML catalog with JSON Schema validation** as the canonical registry format, and keep Markdown frontmatter as the presentation layer for Copilot-native agent files.

Recommended shape:

- `YAML` for the authoritative agent/skill catalog
- `JSON Schema` for validation and versioning
- `.agent.md` files for the user-facing Copilot agent personas
- generated or mirrored registry output for `.agentic/skills.yml` and extension metadata

### Why this is the best fit

1. It matches the repo's existing YAML registry style.
2. It is easy for humans to review and edit.
3. It supports validation without hard-wiring catalog content into Python code.
4. It can be rendered into both agent prompts and machine-readable CLI/MCP output.
5. It keeps the `plate_core` runtime thin: load, validate, expose, and report.

### Proposed minimal catalog fields

At minimum, the baseline catalog should support:

- `id`
- `name`
- `description`
- `primary_skills`
- `constraints`
- `surfaces`
- `examples`
- `version`

## Recommendation

Adopt YAML as the source-of-truth format, validate it with JSON Schema, and keep Markdown frontmatter for the Copilot-facing agent files. Avoid Python dataclasses as the canonical authoring format.

That gives plate_core one durable registry that can be consumed by the CLI, MCP server, plugin bundle, and documentation without fragmenting the catalog across code files.
